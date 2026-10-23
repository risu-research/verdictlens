"""Build a single offline utility HTML from exact V9 audited JSON."""
import json
import pathlib
import sys
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from verdictlens_core import load_audit

def build(output, source):
 data=load_audit(source)
 j=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
 s=(ROOT/'utility_template.html').read_text()
 s=s.replace('__CSS__',(ROOT/'utility_style.css').read_text()).replace('__JS__',(ROOT/'utility_logic.js').read_text().replace('__AUDIT__',j))
 out=pathlib.Path(output);out.write_text(s,encoding='utf-8')
 return out
if __name__=='__main__':
 root=ROOT.parent
 print(build(root/'VerdictLens_Offline.html',root/'data/v9_audit.json'))
