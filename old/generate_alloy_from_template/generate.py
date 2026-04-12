# pipeline to generate the real alloy from the syntax json file and model template

# take in a file name
# a json
# and a model template

# could consider parametrizing out the defense specifics too rather than having a second alloy

# imports
import json, re
from jinja2 import Template

def generate_alloy(outfile="alloy_out.als", template="model_template.als", commented_json="syntax.jsonc"):
  # step 1: clean json
  raw = open(commented_json).read()
  clean = re.sub(r"//.*?$|/\*.*?\*/", "", raw, flags=re.MULTILINE | re.DOTALL)
  cfg = json.loads(clean)

  # step 2: make the alloy
  tmpl = Template(open(template).read())
  open(outfile,"w").write(tmpl.render(**cfg))

generate_alloy()