from typing import List


def model_label(model_name: str, env) -> str:
    return env[model_name]._description or model_name


def fields_meta(model_name: str, env) -> List[dict]:
    fields = env[model_name].fields_get()
    out = []
    for name, f in fields.items():
        out.append({
            "name": name,
            "type": f.get("type"),
            "required": bool(f.get("required")),
            "readonly": bool(f.get("readonly")),
            "string": f.get("string"),
            "selection": f.get("selection") or None,
        })
    return out
