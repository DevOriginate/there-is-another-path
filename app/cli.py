import json, sys
from pathlib import Path
from .models import AssessmentInput
from .engine import evaluate

def main():
    if len(sys.argv)!=2:
        print('Usage: python -m app.cli path/to/assessment.json')
        raise SystemExit(2)
    data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    result=evaluate(AssessmentInput(**data))
    print(result.model_dump_json(indent=2))

if __name__=='__main__':
    main()
