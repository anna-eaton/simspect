#!/usr/bin/env python3
import os
import re
import shlex
import subprocess
import threading
import queue
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

TOTAL_MODELS_RE = re.compile(r"Total models:\s*(\d+)\s*$")

@dataclass
class CmdResult:
    rc: int
    total_models: int | None

class RunnerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Run Panel")
        root.geometry("1120x740")

        self.log_q: queue.Queue[str] = queue.Queue()
        self.proc: subprocess.Popen | None = None

        # --------- EDIT THESE DEFAULTS ONCE ----------
        self.java_workdir = tk.StringVar(value=str(Path.cwd()))   # folder containing CountModels.java
        self.java_classpath = tk.StringVar(value="alloy4.2.jar")             # include Alloy jars here if needed, e.g. "/path/to/alloy.jar:."
        self.java_mainclass = tk.StringVar(value="CountModels")

        # paths to your python scripts
        self.path_batch_xml_to_x86 = tk.StringVar(value="/path/to/batch_xml_to_x86.py")
        self.path_x86_to_llvm = tk.StringVar(value="/path/to/x86_to_llvm.py")  # optional, used in command template below
        # --------------------------------------------

        # CountModels run fields
        self.model_path = tk.StringVar(value="models/STT.als")
        self.out_dir = tk.StringVar(value="alloy-out/STT_out")
        self.limit = tk.StringVar(value="1000")

        # x86 -> llvm (keep as raw command unless you want structured args)
        self.cmd_x86_to_llvm = tk.StringVar(
            value="python3 /path/to/x86_to_llvm.py --in /path/to/in.s --out /path/to/out.ll"
        )

        # XML dir -> x86 fields (matches your batch_xml_to_x86.py)
        self.xml_dir = tk.StringVar(value="")
        self.xml_out = tk.StringVar(value=str(Path.cwd() / "out_llvm"))
        self.xml_glob = tk.StringVar(value="*.xml")
        self.xml_triple = tk.StringVar(value="x86_64-unknown-linux-gnu")
        self.xml_cpu = tk.StringVar(value="x86-64")
        self.xml_link = tk.BooleanVar(value=False)
        self.xml_cc = tk.StringVar(value="clang")
        self.xml_link_all = tk.BooleanVar(value=False)
        self.xml_bin_name = tk.StringVar(value="all_tests")

        # Status
        self.status = tk.StringVar(value="Idle")
        self.total_models_var = tk.StringVar(value="(unknown)")

        self._build_ui()
        self._drain_log_queue()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = self.root

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        java_frame = ttk.LabelFrame(top, text="Java settings", padding=10)
        java_frame.pack(fill="x")

        self._row(java_frame, 0, "Java workdir:", self.java_workdir, browse_cb=lambda: self._browse_dir(self.java_workdir))
        self._row(java_frame, 1, "Java classpath:", self.java_classpath)
        self._row(java_frame, 2, "Main class:", self.java_mainclass)

        btns = ttk.Frame(top, padding=(0, 10, 0, 0))
        btns.pack(fill="x")

        ttk.Button(btns, text="Recompile CountModels (javac)", command=self.on_recompile).pack(side="left")
        ttk.Button(btns, text="Run CountModels", command=self.on_run_countmodels).pack(side="left", padx=8)
        ttk.Button(btns, text="Stop current process", command=self.on_stop).pack(side="left", padx=8)

        cm_frame = ttk.LabelFrame(top, text="CountModels args", padding=10)
        cm_frame.pack(fill="x")

        self._row(cm_frame, 0, "Model (.als):", self.model_path,
                  browse_cb=lambda: self._browse_file(self.model_path, [("Alloy", "*.als"), ("All files", "*.*")]))
        self._row(cm_frame, 1, "Output folder:", self.out_dir,
                  browse_cb=lambda: self._browse_dir(self.out_dir))
        self._row(cm_frame, 2, "Limit:", self.limit)

        stats = ttk.Frame(cm_frame)
        stats.grid(row=3, column=0, columnspan=4, sticky="we", pady=(8, 0))
        ttk.Label(stats, text="Status:").pack(side="left")
        ttk.Label(stats, textvariable=self.status).pack(side="left", padx=(6, 18))
        ttk.Label(stats, text="Total models:").pack(side="left")
        ttk.Label(stats, textvariable=self.total_models_var).pack(side="left", padx=(6, 0))

        tools = ttk.LabelFrame(root, text="Tools", padding=10)
        tools.pack(fill="x", padx=10)

        # x86 -> llvm (raw command)
        self._row(tools, 0, "x86 → LLVM command:", self.cmd_x86_to_llvm)
        ttk.Button(tools, text="Run x86 → LLVM", command=self.on_run_x86_to_llvm).grid(row=0, column=3, padx=8, sticky="w")

        # XML dir -> x86 (structured)
        xml_frame = ttk.LabelFrame(root, text="XML dir → x86 (batch_xml_to_x86.py)", padding=10)
        xml_frame.pack(fill="x", padx=10, pady=(8, 0))

        self._row(xml_frame, 0, "Script path:", self.path_batch_xml_to_x86,
                  browse_cb=lambda: self._browse_file(self.path_batch_xml_to_x86, [("Python", "*.py"), ("All files", "*.*")]))
        self._row(xml_frame, 1, "XML dir:", self.xml_dir, browse_cb=lambda: self._browse_dir(self.xml_dir))
        self._row(xml_frame, 2, "Out dir:", self.xml_out, browse_cb=lambda: self._browse_dir(self.xml_out))
        self._row(xml_frame, 3, "Glob:", self.xml_glob)
        self._row(xml_frame, 4, "Triple:", self.xml_triple)
        self._row(xml_frame, 5, "CPU:", self.xml_cpu)

        flags = ttk.Frame(xml_frame)
        flags.grid(row=6, column=0, columnspan=4, sticky="we", pady=(6, 0))
        ttk.Checkbutton(flags, text="--link", variable=self.xml_link).pack(side="left")
        ttk.Label(flags, text="cc:").pack(side="left", padx=(12, 4))
        ttk.Entry(flags, textvariable=self.xml_cc, width=10).pack(side="left")

        ttk.Checkbutton(flags, text="--link-all", variable=self.xml_link_all).pack(side="left", padx=(12, 0))
        ttk.Label(flags, text="bin name:").pack(side="left", padx=(12, 4))
        ttk.Entry(flags, textvariable=self.xml_bin_name, width=16).pack(side="left")

        ttk.Button(xml_frame, text="Run XML dir → x86", command=self.on_run_xml_dir_to_x86).grid(
            row=7, column=0, sticky="w", pady=(8, 0)
        )

        log_frame = ttk.LabelFrame(root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log = tk.Text(log_frame, wrap="word", height=18)
        self.log.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)

        self.log.insert("end", "Ready.\n")

    def _row(self, parent, r, label, var, browse_cb=None):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w")
        e = ttk.Entry(parent, textvariable=var)
        e.grid(row=r, column=1, sticky="we", padx=8)
        parent.grid_columnconfigure(1, weight=1)
        if browse_cb:
            ttk.Button(parent, text="Browse", command=browse_cb).grid(row=r, column=2, sticky="w")

    def _browse_file(self, var: tk.StringVar, types):
        p = filedialog.askopenfilename(filetypes=types)
        if p:
            var.set(p)

    def _browse_dir(self, var: tk.StringVar):
        p = filedialog.askdirectory()
        if p:
            var.set(p)

    # --------------- Actions ---------------
    def on_recompile(self):
        workdir = self._require_dir(self.java_workdir.get(), "Java workdir")
        cmd = "javac CountModels.java"
        cmd = "javac -cp alloy4.2.jar:. CountModels.java"
        # ["javac", "-cp", "alloy4.2.jar:.", "CountModels.java"]
        self._run_shell(cmd, cwd=workdir, label="javac")

    def on_run_countmodels(self):
        workdir = self._require_dir(self.java_workdir.get(), "Java workdir")
        cp = self.java_classpath.get().strip()
        maincls = self.java_mainclass.get().strip()
        model = self.model_path.get().strip()
        outdir = self.out_dir.get().strip()
        limit = self.limit.get().strip()

        if not model:
            messagebox.showerror("Missing input", "Pick a model (.als).")
            return
        if not outdir:
            messagebox.showerror("Missing output", "Pick an output folder.")
            return
        try:
            Path(outdir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Bad output folder", str(e))
            return

        if limit:
            cmd = f'java -cp {shlex.quote(cp)} {shlex.quote(maincls)} {shlex.quote(model)} {shlex.quote(outdir)} {shlex.quote(limit)}'
        else:
            cmd = f'java -cp {shlex.quote(cp)} {shlex.quote(maincls)} {shlex.quote(model)} {shlex.quote(outdir)}'

        self.total_models_var.set("(unknown)")
        self._run_shell(cmd, cwd=workdir, label="CountModels", parse_total_models=True)

    def on_run_x86_to_llvm(self):
        cmd = self.cmd_x86_to_llvm.get().strip()
        if not cmd or "/path/to/" in cmd:
            messagebox.showwarning("Edit command", "Set a real x86 → LLVM command first.")
            return
        self._run_shell(cmd, cwd=None, label="x86→LLVM")

    def on_run_xml_dir_to_x86(self):
        script = self.path_batch_xml_to_x86.get().strip()
        xml_dir = self.xml_dir.get().strip()
        out_dir = self.xml_out.get().strip()
        glob = self.xml_glob.get().strip()
        triple = self.xml_triple.get().strip()
        cpu = self.xml_cpu.get().strip()
        cc = self.xml_cc.get().strip()
        bin_name = self.xml_bin_name.get().strip()

        if not script or not Path(script).exists():
            messagebox.showerror("Bad script path", f"Script not found:\n{script}")
            return
        if not xml_dir:
            messagebox.showerror("Missing XML dir", "Pick the folder containing inst-*.xml files.")
            return
        if not Path(xml_dir).is_dir():
            messagebox.showerror("Bad XML dir", f"Not a directory:\n{xml_dir}")
            return
        if not out_dir:
            messagebox.showerror("Missing out dir", "Pick an output directory.")
            return

        args = [
            "python3",
            script,
            xml_dir,
            "--out", out_dir,
            "--glob", glob,
            "--triple", triple,
            "--cpu", cpu,
        ]
        if self.xml_link.get():
            args += ["--link", "--cc", cc]
        if self.xml_link_all.get():
            args += ["--link-all", "--bin-name", bin_name, "--cc", cc]

        cmd = " ".join(shlex.quote(a) for a in args)
        self._run_shell(cmd, cwd=None, label="XMLdir→x86")

    def on_stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self._log("[stop] Sent terminate.\n")
            except Exception as e:
                self._log(f"[stop] Failed: {e}\n")
        else:
            self._log("[stop] No running process.\n")

    # --------------- Process runner ---------------
    def _run_shell(self, cmd: str, cwd: str | None, label: str, parse_total_models: bool = False):
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("Busy", "A process is already running. Stop it first.")
            return

        self.status.set(f"Running: {label}")
        self._log(f"\n=== {label} ===\n$ {cmd}\n")
        self._log(f"(cwd: {cwd or os.getcwd()})\n")

        def worker():
            total_models = None
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    executable="/bin/bash" if os.name != "nt" else None,
                )

                assert self.proc.stdout is not None
                for line in self.proc.stdout:
                    self.log_q.put(line)
                    if parse_total_models:
                        m = TOTAL_MODELS_RE.search(line.strip())
                        if m:
                            total_models = int(m.group(1))

                rc = self.proc.wait()
                self.log_q.put(f"[exit] rc={rc}\n")
                self._on_process_done(CmdResult(rc=rc, total_models=total_models), label)

            except Exception as e:
                self.log_q.put(f"[error] {e}\n")
                self._on_process_done(CmdResult(rc=1, total_models=None), label)

        threading.Thread(target=worker, daemon=True).start()

    def _on_process_done(self, res: CmdResult, label: str):
        def update():
            if label == "CountModels" and res.total_models is not None:
                self.total_models_var.set(str(res.total_models))
            self.status.set("Idle")
        self.root.after(0, update)

    # --------------- Logging ---------------
    def _drain_log_queue(self):
        try:
            while True:
                s = self.log_q.get_nowait()
                self._log(s)
        except queue.Empty:
            pass
        self.root.after(50, self._drain_log_queue)

    def _log(self, s: str):
        self.log.insert("end", s)
        self.log.see("end")

    # --------------- Helpers ---------------
    def _require_dir(self, path: str, name: str) -> str:
        p = Path(path).expanduser()
        if not p.exists() or not p.is_dir():
            messagebox.showerror("Bad path", f"{name} is not a directory:\n{p}")
            raise SystemExit(1)
        return str(p)

def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    RunnerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
