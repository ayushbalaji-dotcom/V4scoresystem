import base64
import json
import os
import re
import uuid
from copy import deepcopy
from typing import Dict, List, Tuple
from urllib import request, error

try:
    from google import genai
except Exception:  # pragma: no cover
    genai = None

import streamlit as st

DATA_PATH = os.path.join("data", "tools.json")
GITHUB_REPO = "ayushbalaji-dotcom/homepagev2"
GITHUB_BRANCH = "main"
GITHUB_CALCULATORS_DIR = "calculators"

CATEGORIES = {
    "Cardiac": ["Coronary", "Aortic", "Tricuspid", "Mitral", "Pulmonary", "Arrhythmia", "Miscellaneous"],
    "Thoracic": ["Malignant", "Benign"],
    "Transplant": [],
}
GEMINI_MODEL = "gemini-2.5-flash"

DEFAULT_TOOL = {
    "name": "New Tool",
    "description": "",
    "inputs": [],
    "scoring_rules": [],
    "rules": [],
    "scoring_recommendations": [],
    "scoring_mode": "signed",
}

TRICUSPID_TOOL = {
    "name": "Concomitant Tricuspid Repair Evaluator",
    "description": "Fill out the clinical data below to see guideline recommendations.",
    "inputs": [
        {
            "id": "left_sided_valve_surgery",
            "label": "Has the patient had left-sided valve surgery?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "tr_severity",
            "label": "What is the TR severity?",
            "type": "select",
            "options": ["Mild", "Moderate", "Severe"],
        },
        {
            "id": "tr_mechanism",
            "label": "What is the TR mechanism?",
            "type": "select",
            "options": ["Primary", "Secondary (functional)"],
        },
        {
            "id": "annulus_dilated",
            "label": "Tricuspid annulus dilated?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "atrial_fib",
            "label": "Chronic atrial fibrillation?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "ra_dilatation",
            "label": "Significant right atrial dilatation?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "rv_dysfunction",
            "label": "RV dilatation or dysfunction?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "tethering",
            "label": "Non-severe leaflet tethering?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "phtn",
            "label": "Pulmonary hypertension present?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "organ_dysfunction",
            "label": "Reversible renal/liver dysfunction?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "conduction_disease",
            "label": "Is there Conduction disease?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
        {
            "id": "no_comorbidities",
            "label": "No other relevant comorbidities?",
            "type": "select",
            "options": ["Yes", "No", "Unknown"],
        },
    ],
    "scoring_rules": [
        {
            "input_id": "tr_severity",
            "favor_values": ["Moderate", "Severe"],
            "against_values": ["Mild"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "annulus_dilated",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "atrial_fib",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "ra_dilatation",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "rv_dysfunction",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "tethering",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "phtn",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "organ_dysfunction",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        },
        {
            "input_id": "conduction_disease",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": True,
            "weight": 1,
        },
        {
            "input_id": "no_comorbidities",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": True,
            "weight": 1,
        },
    ],
    "rules": [
        {
            "name": "Class 1",
            "level": "success",
            "message": "Class 1: Concomitant TR Repair Recommended",
            "conditions": [{"input_id": "tr_severity", "op": "equals", "value": "Severe"}],
        },
        {
            "name": "Class 2a",
            "level": "info",
            "message": "Class 2a: Concomitant TR Repair should be considered",
            "conditions": [{"input_id": "tr_severity", "op": "equals", "value": "Moderate"}],
        },
        {
            "name": "Class 2b",
            "level": "warning",
            "message": "Class 2b: Concomitant TR Repair may be considered",
            "conditions": [
                {"input_id": "tr_severity", "op": "equals", "value": "Mild"},
                {"input_id": "tr_mechanism", "op": "equals", "value": "Secondary (functional)"},
                {"input_id": "annulus_dilated", "op": "equals", "value": "Yes"},
            ],
        },
    ],
    "fallback": {
        "level": "warning",
        "message": "Class 1c: Careful Evaluation / MDT Recommended prior to consideration of intervention",
    },
}

LEVELS = ["success", "info", "warning", "error"]
INPUT_TYPES = ["select", "number", "text"]


def load_tools():
    if not os.path.exists(DATA_PATH):
        return {"tools": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tools(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_github_token():
    return st.secrets.get("github_token") or os.environ.get("GITHUB_TOKEN")


def parse_free_text_rule(text: str, scoring_mode: str) -> Dict:
    if genai is None:
        raise RuntimeError("Google GenAI client not available. Install google-genai.")
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing Gemini API key. Add GEMINI_API_KEY to Streamlit secrets.")
    client = genai.Client(api_key=api_key)

    json_schema = {
        "type": "object",
        "properties": {
            "inputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "type": {"type": "string", "enum": ["select", "number", "text"]},
                        "options": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["label", "type", "options"],
                },
            },
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "level": {"type": "string", "enum": ["success", "info", "warning", "error"]},
                        "message": {"type": "string"},
                        "condition_operator": {"type": "string", "enum": ["AND", "OR"]},
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                                "required": ["label", "value"],
                            },
                        },
                    },
                    "required": ["name", "level", "message", "condition_operator", "conditions"],
                },
            },
            "scoring_rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "favor_values": {"type": "array", "items": {"type": "string"}},
                        "against_values": {"type": "array", "items": {"type": "string"}},
                        "invert_favor": {"type": "boolean"},
                        "weight": {"type": "integer"},
                    },
                    "required": ["label", "favor_values", "against_values", "invert_favor", "weight"],
                },
            },
            "scoring_recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "min_score": {"type": "integer"},
                        "level": {"type": "string", "enum": ["success", "info", "warning", "error"]},
                        "message": {"type": "string"},
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                                "required": ["label", "value"],
                            },
                        },
                    },
                    "required": ["min_score", "level", "message", "conditions"],
                },
            },
        },
        "required": ["inputs", "rules", "scoring_rules", "scoring_recommendations"],
    }

    scoring_line = (
        "If scoring_mode is 'positive-only', do not create against_values; use only favor_values. "
        "If scoring_mode is 'signed', you may use both favor_values and against_values."
    )
    system_prompt = (
        "You convert free-text clinical decision rules into structured inputs, scoring rules, and recommendation rules. "
        "Always return valid JSON matching the schema. "
        "Use select inputs with options ['Yes','No','Unknown'] for boolean concepts. "
        "If the text mentions severity (mild/moderate/severe), create a select input with those options. "
        "All labels must be phrased as questions (e.g., 'Does the patient have atrial fibrillation?'). "
        "Return multiple recommendation rules when the text describes alternatives or exceptions. "
        "Set condition_operator to 'OR' when the recommendation is triggered by any one condition; otherwise use 'AND'. "
        "Create scoring rules when you see favorable vs unfavorable factors; otherwise return an empty scoring_rules list. "
        "If the text describes score thresholds, populate scoring_recommendations with min_score and message. "
        "If thresholds depend on another factor (e.g., sex), include that as a condition on the scoring_recommendation. "
        "If the text includes a class label (e.g., Class I, Class IIa, Class 1B), include that phrase in the rule message (and optionally the rule name). "
        + scoring_line
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[f"{system_prompt}\nscoring_mode={scoring_mode}", text],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": json_schema,
        },
    )

    return json.loads(response.text)


def github_request(method: str, url: str, token: str, payload: Dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "score-builder-v3",
        "Authorization": f"Bearer {token}",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, method=method, headers=headers, data=data)
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tool_id_from_github_path(path: str) -> str:
    return "gh_" + re.sub(r"[^a-zA-Z0-9_]+", "_", path).strip("_").lower()


def list_github_calculator_paths(token: str) -> List[str]:
    def walk(dir_path: str) -> List[str]:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{dir_path}?ref={GITHUB_BRANCH}"
        entries = github_request("GET", url, token)
        paths: List[str] = []
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries:
            if entry.get("type") == "dir":
                paths.extend(walk(entry.get("path", "")))
            elif entry.get("type") == "file" and safe_str(entry.get("name")).endswith(".json"):
                paths.append(entry.get("path"))
        return paths

    return walk(GITHUB_CALCULATORS_DIR)


def parse_category_from_github_path(path: str) -> Tuple[str, str]:
    parts = path.split("/")
    # calculators/<category>/<subcategory>/<file>.json
    category = parts[1] if len(parts) >= 3 else "Cardiac"
    subcategory = parts[2] if len(parts) >= 4 else ""
    return category, subcategory


def sync_tools_from_github(data: Dict) -> Tuple[Dict, int, str]:
    token = get_github_token()
    if not token:
        return data, 0, "Skipping GitHub sync (missing token)."

    try:
        paths = list_github_calculator_paths(token)
    except Exception as exc:
        return data, 0, f"GitHub sync failed: {exc}"

    tools = data.setdefault("tools", {})
    by_path = {
        safe_str(t.get("github_path")): tool_id
        for tool_id, t in tools.items()
        if safe_str(t.get("github_path"))
    }
    synced = 0

    for path in paths:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
            content_obj = github_request("GET", url, token)
            encoded = safe_str(content_obj.get("content")).replace("\n", "")
            parsed = json.loads(base64.b64decode(encoded).decode("utf-8"))
        except Exception:
            continue

        category, subcategory = parse_category_from_github_path(path)
        parsed["category"] = category
        parsed["subcategory"] = subcategory
        parsed["github_path"] = path

        tool_id = by_path.get(path) or tool_id_from_github_path(path)
        tools[tool_id] = parsed
        synced += 1

    return data, synced, f"Synced {synced} calculators from GitHub."


def save_tool_to_github(tool: Dict) -> Tuple[bool, str, str]:
    token = get_github_token()
    if not token:
        return False, "Missing GitHub token. Add github_token to Streamlit secrets.", ""

    filename = f"{safe_str(tool.get('name','tool')).replace(' ', '_').lower() or 'tool'}.json"
    category = safe_str(tool.get("category")) or "Uncategorized"
    subcategory = safe_str(tool.get("subcategory"))
    target_path = f"{GITHUB_CALCULATORS_DIR}/{category}/{subcategory}/{filename}" if subcategory else f"{GITHUB_CALCULATORS_DIR}/{category}/{filename}"

    previous_path = safe_str(tool.get("github_path"))
    path = previous_path or target_path
    if previous_path and previous_path != target_path:
        # Treat category/name change as a move: write new path, then delete old.
        path = target_path

    if subcategory and not previous_path:
        path = target_path
    else:
        path = target_path
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

    existing_sha = None
    try:
        existing = github_request("GET", f"{url}?ref={GITHUB_BRANCH}", token)
        existing_sha = existing.get("sha")
    except error.HTTPError as exc:
        if exc.code != 404:
            return False, f"GitHub lookup failed: {exc}", ""

    content = json.dumps(tool, indent=2).encode("utf-8")
    payload = {
        "message": f"Add/Update calculator {filename}",
        "content": base64.b64encode(content).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    try:
        github_request("PUT", url, token, payload)
        if previous_path and previous_path != target_path:
            old_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{previous_path}"
            try:
                old = github_request("GET", f"{old_url}?ref={GITHUB_BRANCH}", token)
                old_sha = old.get("sha")
                if old_sha:
                    github_request(
                        "DELETE",
                        old_url,
                        token,
                        {"message": f"Move calculator to {target_path}", "sha": old_sha, "branch": GITHUB_BRANCH},
                    )
            except Exception:
                pass
        return True, f"Saved to GitHub: {path}", path
    except error.HTTPError as exc:
        return False, f"GitHub save failed: {exc}", ""


def delete_tool_from_github(tool: Dict) -> Tuple[bool, str]:
    token = get_github_token()
    if not token:
        return False, "Missing GitHub token. Add github_token to Streamlit secrets."

    filename = f"{safe_str(tool.get('name','tool')).replace(' ', '_').lower() or 'tool'}.json"
    category = safe_str(tool.get("category")) or "Uncategorized"
    subcategory = safe_str(tool.get("subcategory"))
    path = safe_str(tool.get("github_path"))
    if not path:
        if subcategory:
            path = f"{GITHUB_CALCULATORS_DIR}/{category}/{subcategory}/{filename}"
        else:
            path = f"{GITHUB_CALCULATORS_DIR}/{category}/{filename}"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

    try:
        existing = github_request("GET", f"{url}?ref={GITHUB_BRANCH}", token)
        existing_sha = existing.get("sha")
        if not existing_sha:
            return False, "File not found on GitHub."
    except error.HTTPError as exc:
        if exc.code == 404:
            return False, "File not found on GitHub."
        return False, f"GitHub lookup failed: {exc}"

    payload = {
        "message": f"Delete calculator {filename}",
        "sha": existing_sha,
        "branch": GITHUB_BRANCH,
    }

    try:
        github_request("DELETE", url, token, payload)
        return True, f"Deleted from GitHub: {path}"
    except error.HTTPError as exc:
        return False, f"GitHub delete failed: {exc}"


def ensure_state():
    if "tools_data" not in st.session_state:
        st.session_state.tools_data = load_tools()
        tools = st.session_state.tools_data.setdefault("tools", {})
        if "tricuspid_repair" not in tools:
            tools["tricuspid_repair"] = deepcopy(TRICUSPID_TOOL)
            save_tools(st.session_state.tools_data)
        st.session_state.tools_data, synced_count, sync_message = sync_tools_from_github(st.session_state.tools_data)
        st.session_state.github_sync_message = sync_message
        st.session_state.github_synced_count = synced_count
        save_tools(st.session_state.tools_data)
    if "selected_tool_id" not in st.session_state:
        tool_ids = list(st.session_state.tools_data.get("tools", {}).keys())
        st.session_state.selected_tool_id = tool_ids[0] if tool_ids else None
    if "editing_tool" not in st.session_state:
        st.session_state.editing_tool = None
    if "editing_tool_id" not in st.session_state:
        st.session_state.editing_tool_id = None
    if "preview_values" not in st.session_state:
        st.session_state.preview_values = {}
    if "github_sync_message" not in st.session_state:
        st.session_state.github_sync_message = ""
    if "github_synced_count" not in st.session_state:
        st.session_state.github_synced_count = 0


def normalize_options(options_csv):
    if not options_csv:
        return []
    if isinstance(options_csv, list):
        return [str(o).strip() for o in options_csv if str(o).strip()]
    return [o.strip() for o in str(options_csv).split(",") if o.strip()]


def safe_str(value):
    if value is None:
        return ""
    return str(value).strip()


def slugify(value: str) -> str:
    value = safe_str(value).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def ensure_input_ids(inputs: List[Dict]) -> List[Dict]:
    for item in inputs:
        if not safe_str(item.get("id")):
            item["id"] = slugify(item.get("label", ""))
    return inputs


def build_label_maps(inputs: List[Dict]) -> Tuple[Dict[str, str], Dict[str, str]]:
    id_to_label = {}
    label_to_id = {}
    for item in inputs:
        input_id = safe_str(item.get("id"))
        label = safe_str(item.get("label")) or input_id
        if input_id:
            id_to_label[input_id] = label
            label_to_id[label] = input_id
    return id_to_label, label_to_id


def get_input_options(inputs: List[Dict], input_id: str) -> List[str]:
    for item in inputs:
        if safe_str(item.get("id")) == input_id:
            return item.get("options", []) or []
    return []


def questionize_label(label: str) -> str:
    label = safe_str(label)
    if not label:
        return ""
    if label.endswith("?"):
        return label
    starts = label.lower().strip()
    question_starts = (
        "what",
        "which",
        "when",
        "how",
        "is",
        "are",
        "does",
        "do",
        "did",
        "has",
        "have",
        "was",
        "were",
        "can",
        "should",
        "could",
        "would",
        "will",
    )
    if starts.startswith(question_starts):
        return f"{label}?"
    return f"Does the patient have {label}?"


def merge_ai_result(tool: Dict, parsed: Dict) -> Dict:
    inputs = tool.get("inputs", [])
    existing_labels = {
        safe_str(item.get("label")) for item in inputs if safe_str(item.get("label"))
    }

    for item in parsed.get("inputs", []):
        label = questionize_label(item.get("label"))
        if not label or label in existing_labels:
            continue
        input_id = slugify(label)
        inputs.append(
            {
                "id": input_id,
                "label": label,
                "type": item.get("type", "select"),
                "options": item.get("options", []),
            }
        )
        existing_labels.add(label)

    tool["inputs"] = inputs
    id_to_label, label_to_id = build_label_maps(inputs)

    for rule in parsed.get("rules", []):
        conditions = []
        for cond in rule.get("conditions", []):
            label = questionize_label(cond.get("label"))
            value = safe_str(cond.get("value"))
            input_id = label_to_id.get(label)
            if input_id and value:
                conditions.append({"input_id": input_id, "op": "equals", "value": value})

        if conditions:
            tool.setdefault("rules", []).append(
                {
                    "name": safe_str(rule.get("name")) or "AI Rule",
                    "level": rule.get("level", "info"),
                    "message": safe_str(rule.get("message")),
                    "condition_operator": safe_str(rule.get("condition_operator", "AND")).upper() or "AND",
                    "conditions": conditions,
                }
            )

    scoring_rules = tool.get("scoring_rules", [])
    for srule in parsed.get("scoring_rules", []):
        label = questionize_label(srule.get("label"))
        input_id = label_to_id.get(label)
        if not input_id:
            continue
        scoring_rules.append(
            {
                "input_id": input_id,
                "favor_values": srule.get("favor_values", []),
                "against_values": srule.get("against_values", []),
                "invert_favor": bool(srule.get("invert_favor", False)),
                "weight": int(srule.get("weight", 1) or 1),
            }
        )
    tool["scoring_rules"] = scoring_rules

    scoring_recs = tool.get("scoring_recommendations", [])
    for item in parsed.get("scoring_recommendations", []):
        conditions = []
        for cond in item.get("conditions", []):
            label = questionize_label(cond.get("label"))
            value = safe_str(cond.get("value"))
            input_id = label_to_id.get(label)
            if input_id and value:
                conditions.append({"input_id": input_id, "op": "equals", "value": value})
        try:
            min_score = int(item.get("min_score"))
        except (TypeError, ValueError):
            continue
        scoring_recs.append(
            {
                "min_score": min_score,
                "level": item.get("level", "info"),
                "message": safe_str(item.get("message")),
                "conditions": conditions,
            }
        )
    tool["scoring_recommendations"] = scoring_recs

    return tool

def tool_to_input_rows(tool):
    rows = []
    for item in tool.get("inputs", []):
        rows.append(
            {
                "label": item.get("label", ""),
                "type": item.get("type", "select"),
                "options_csv": ", ".join(item.get("options", [])),
            }
        )
    return rows


def input_rows_to_tool(rows, existing_inputs):
    inputs = []
    existing_by_label = {
        safe_str(item.get("label")): safe_str(item.get("id"))
        for item in existing_inputs
        if safe_str(item.get("label"))
    }
    for row in rows:
        if not row.get("label"):
            continue
        label = safe_str(row.get("label", ""))
        input_id = existing_by_label.get(label) or slugify(label)
        inputs.append(
            {
                "id": input_id,
                "label": label,
                "type": row.get("type", "select"),
                "options": normalize_options(row.get("options_csv", "")),
            }
        )
    return inputs


def tool_to_scoring_rows(tool):
    rows = []
    for item in tool.get("scoring_rules", []):
        rows.append(
            {
                "input_id": item.get("input_id", ""),
                "favor_values_csv": ", ".join(item.get("favor_values", [])),
                "against_values_csv": ", ".join(item.get("against_values", [])),
                "invert_favor": bool(item.get("invert_favor", False)),
                "weight": int(item.get("weight", 1)),
            }
        )
    return rows


def scoring_rows_to_tool(rows):
    rules = []
    for row in rows:
        if not row.get("input_id"):
            continue
        weight_value = row.get("weight", 1)
        try:
            weight_value = int(weight_value)
        except (TypeError, ValueError):
            weight_value = 1
        if weight_value < 1:
            weight_value = 1
        rules.append(
            {
                "input_id": safe_str(row.get("input_id")),
                "favor_values": normalize_options(row.get("favor_values_csv", "")),
                "against_values": normalize_options(row.get("against_values_csv", "")),
                "invert_favor": bool(row.get("invert_favor", False)),
                "weight": weight_value,
            }
        )
    return rules


def tool_to_rule_rows(tool):
    rows = []
    for rule in tool.get("rules", []):
        conditions = rule.get("conditions", [])
        row = {
            "name": rule.get("name", ""),
            "level": rule.get("level", "info"),
            "message": rule.get("message", ""),
        }
        for idx in range(3):
            key_id = f"input_id_{idx + 1}"
            key_val = f"value_{idx + 1}"
            if idx < len(conditions):
                row[key_id] = conditions[idx].get("input_id", "")
                row[key_val] = conditions[idx].get("value", "")
            else:
                row[key_id] = ""
                row[key_val] = ""
        rows.append(row)
    return rows


def rule_rows_to_tool(rows):
    rules = []
    for row in rows:
        if not row.get("name"):
            continue
        conditions = []
        for idx in range(3):
            input_id = safe_str(row.get(f"input_id_{idx + 1}", ""))
            value = row.get(f"value_{idx + 1}", "")
            if input_id and value != "":
                conditions.append({"input_id": input_id, "op": "equals", "value": value})
        rules.append(
            {
                "name": row.get("name", ""),
                "level": row.get("level", "info"),
                "message": row.get("message", ""),
                "conditions": conditions,
            }
        )
    return rules


def ensure_editing_tool():
    tool_id = st.session_state.selected_tool_id
    if tool_id is None:
        st.session_state.editing_tool = None
        st.session_state.editing_tool_id = None
        return
    if st.session_state.editing_tool is None or st.session_state.editing_tool_id != tool_id:
        current = st.session_state.tools_data["tools"].get(tool_id)
        st.session_state.editing_tool = deepcopy(current)
        st.session_state.editing_tool_id = tool_id


def render_message(level, message):
    if level == "success":
        st.success(message)
    elif level == "info":
        st.info(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.error(message)


def evaluate_rules(tool, values):
    def condition_match(cond: Dict) -> bool:
        input_id = cond.get("input_id")
        expected = cond.get("value")
        return values.get(input_id) == expected

    def evaluate_condition_expression(rule: Dict) -> Tuple[bool, int, float, int]:
        conditions = rule.get("conditions", [])
        if not conditions:
            return False, 0, 0.0, 0

        default_join = safe_str(rule.get("condition_operator", "AND")).upper()
        if default_join not in {"AND", "OR"}:
            default_join = "AND"

        matched_count = 0
        first_match = condition_match(conditions[0])
        if first_match:
            matched_count += 1
        current_group = first_match
        group_results: List[bool] = []

        for cond in conditions[1:]:
            cond_is_match = condition_match(cond)
            if cond_is_match:
                matched_count += 1
            join = safe_str(cond.get("join_with_previous", default_join)).upper()
            if join not in {"AND", "OR"}:
                join = default_join
            if join == "AND":
                current_group = current_group and cond_is_match
            else:
                group_results.append(current_group)
                current_group = cond_is_match

        group_results.append(current_group)
        is_match = any(group_results)
        ratio = matched_count / len(conditions)
        return is_match, matched_count, ratio, len(conditions)

    best_match = None
    best_count = 0
    best_ratio = 0.0
    best_total_conditions = 0
    for rule in tool.get("rules", []):
        is_match, matched, ratio, condition_count = evaluate_condition_expression(rule)
        if not is_match:
            continue
        if ratio == 1.0 and best_ratio == 1.0:
            if condition_count > best_total_conditions:
                best_count = matched
                best_ratio = ratio
                best_total_conditions = condition_count
                best_match = rule
                continue
        if matched > best_count or (matched == best_count and ratio > best_ratio):
            best_count = matched
            best_ratio = ratio
            best_total_conditions = condition_count
            best_match = rule

    if best_match and best_count > 0:
        return best_match.get("level", "info"), best_match.get("message", "")

    return None, None


def compute_scores(tool, values):
    plus = 0
    minus = 0
    scoring_mode = tool.get("scoring_mode", "signed")
    for rule in tool.get("scoring_rules", []):
        input_id = rule.get("input_id")
        if not input_id:
            continue
        value = values.get(input_id)
        favor_values = rule.get("favor_values", [])
        against_values = rule.get("against_values", [])
        invert = rule.get("invert_favor", False)
        weight = rule.get("weight", 1) or 1
        score = 0
        if value in favor_values:
            score = -1 if invert else 1
        elif value in against_values:
            score = 1 if invert else -1
        if score == 1:
            plus += weight
        elif score == -1 and scoring_mode == "signed":
            minus += weight
    total = plus - minus if scoring_mode == "signed" else plus
    return plus, minus, total


def evaluate_score_recommendation(tool, values, total_score):
    thresholds = tool.get("scoring_recommendations", [])
    if not thresholds:
        return None
    best = None
    for item in thresholds:
        try:
            min_score = int(item.get("min_score"))
        except (TypeError, ValueError):
            continue
        if total_score >= min_score:
            conditions = item.get("conditions", [])
            matched = 0
            for cond in conditions:
                input_id = cond.get("input_id")
                expected = cond.get("value")
                actual = values.get(input_id)
                if actual == expected:
                    matched += 1
            if conditions and matched != len(conditions):
                continue
            ratio = matched / len(conditions) if conditions else 1.0
            candidate = {
                "min_score": min_score,
                "level": item.get("level", "info"),
                "message": item.get("message", ""),
                "matched": matched,
                "ratio": ratio,
            }
            if best is None:
                best = candidate
            else:
                if min_score > best.get("min_score", -10**9):
                    best = candidate
                elif min_score == best.get("min_score", -10**9) and ratio > best.get("ratio", 0.0):
                    best = candidate
    return best


def build_decision_tree_graph(tool: Dict, id_to_label: Dict[str, str]) -> str:
    lines = ["digraph DecisionTree {", 'rankdir=LR;', 'node [shape=box, style="rounded"];']
    lines.append('start [label="Start"];')
    for ridx, rule in enumerate(tool.get("rules", [])):
        rule_node = f"rule_{ridx}"
        rule_label = safe_str(rule.get("name")) or f"Rule {ridx + 1}"
        lines.append(f'{rule_node} [label="{rule_label}"];')
        lines.append(f"start -> {rule_node};")

        prev_node = rule_node
        for cidx, cond in enumerate(rule.get("conditions", [])):
            cond_node = f"rule_{ridx}_cond_{cidx}"
            input_label = id_to_label.get(cond.get("input_id", ""), cond.get("input_id", ""))
            value = safe_str(cond.get("value"))
            cond_label = f"{input_label} = {value}".replace('"', "'")
            lines.append(f'{cond_node} [label="{cond_label}"];')
            edge_label = ""
            if cidx > 0:
                edge_label = safe_str(cond.get("join_with_previous", "AND")).upper()
            if edge_label:
                lines.append(f'{prev_node} -> {cond_node} [label="{edge_label}"];')
            else:
                lines.append(f"{prev_node} -> {cond_node};")
            prev_node = cond_node

        out_node = f"rule_{ridx}_out"
        msg = safe_str(rule.get("message")) or "Recommendation"
        msg = msg.replace('"', "'")
        lines.append(f'{out_node} [shape=note, label="{msg}"];')
        lines.append(f"{prev_node} -> {out_node};")

    lines.append("}")
    return "\n".join(lines)


def main():
    st.set_page_config(page_title="Tool Builder", layout="wide")
    st.title("Tool Builder")
    st.caption("Build and run decision tools in the same app. Save multiple tools and preview live.")

    ensure_state()

    with st.sidebar:
        st.subheader("Tools")
        tool_items = st.session_state.tools_data.get("tools", {})
        tool_ids = list(tool_items.keys())
        tool_labels = [tool_items[tool_id]["name"] for tool_id in tool_ids]

        if tool_ids:
            previous_selection = st.session_state.selected_tool_id
            selected_label = st.selectbox(
                "Select tool",
                options=tool_labels,
                index=tool_ids.index(st.session_state.selected_tool_id)
                if st.session_state.selected_tool_id in tool_ids
                else 0,
            )
            st.session_state.selected_tool_id = tool_ids[tool_labels.index(selected_label)]
            if st.session_state.selected_tool_id != previous_selection:
                st.session_state.editing_tool = None
                st.session_state.editing_tool_id = None
        else:
            st.info("No tools yet. Create your first tool.")

        if st.button("New Tool"):
            new_id = f"tool_{uuid.uuid4().hex[:8]}"
            st.session_state.tools_data["tools"][new_id] = deepcopy(DEFAULT_TOOL)
            st.session_state.selected_tool_id = new_id
            save_tools(st.session_state.tools_data)
            st.rerun()

        if st.button("Reset Defaults"):
            st.session_state.tools_data.setdefault("tools", {})
            st.session_state.tools_data["tools"]["tricuspid_repair"] = deepcopy(TRICUSPID_TOOL)
            save_tools(st.session_state.tools_data)
            st.session_state.selected_tool_id = "tricuspid_repair"
            st.rerun()

        if st.button("Sync from GitHub"):
            st.session_state.tools_data, synced_count, sync_message = sync_tools_from_github(st.session_state.tools_data)
            st.session_state.github_synced_count = synced_count
            st.session_state.github_sync_message = sync_message
            save_tools(st.session_state.tools_data)
            st.rerun()

        if st.session_state.github_sync_message:
            st.caption(st.session_state.github_sync_message)

        if tool_ids:
            if st.button("Delete Tool"):
                del st.session_state.tools_data["tools"][st.session_state.selected_tool_id]
                save_tools(st.session_state.tools_data)
                remaining_ids = list(st.session_state.tools_data.get("tools", {}).keys())
                st.session_state.selected_tool_id = remaining_ids[0] if remaining_ids else None
                st.rerun()

    if st.session_state.selected_tool_id is None:
        st.stop()

    ensure_editing_tool()
    tool = st.session_state.editing_tool

    tabs = st.tabs(["Builder", "Preview"])

    with tabs[0]:
        st.subheader("Tool Details")
        tool["name"] = st.text_input("Tool name", value=tool.get("name", ""))
        tool["description"] = st.text_area("Description", value=tool.get("description", ""))
        col_a, col_b = st.columns(2)
        with col_a:
            category = st.selectbox(
                "Section",
                options=list(CATEGORIES.keys()),
                index=list(CATEGORIES.keys()).index(tool.get("category", "Cardiac"))
                if tool.get("category", "Cardiac") in CATEGORIES
                else 0,
            )
        with col_b:
            subcats = CATEGORIES.get(category, [])
            if subcats:
                subcategory = st.selectbox(
                    "Subsection",
                    options=subcats,
                    index=subcats.index(tool.get("subcategory", subcats[0]))
                    if tool.get("subcategory") in subcats
                    else 0,
                )
            else:
                subcategory = ""
                st.text_input("Subsection", value="(none)", disabled=True)
        tool["category"] = category
        tool["subcategory"] = subcategory
        scoring_mode = st.selectbox(
            "Scoring mode",
            ["signed", "positive-only"],
            index=["signed", "positive-only"].index(tool.get("scoring_mode", "signed")),
            format_func=lambda x: "Signed (favor + / against -)" if x == "signed" else "Positive-only (no negatives)",
        )
        tool["scoring_mode"] = scoring_mode

        st.divider()
        st.subheader("Free-Text Rule Builder (AI)")
        st.caption("Paste a guideline sentence and let AI propose inputs + a rule. You can edit afterwards.")
        free_text = st.text_area(
            "Rule text",
            value=st.session_state.get("free_text_rule", ""),
            key="free_text_rule",
            height=120,
        )
        scoring_hint = st.selectbox(
            "Scoring style for AI parser",
            ["signed", "positive-only"],
            index=["signed", "positive-only"].index(tool.get("scoring_mode", "signed")),
            format_func=lambda x: "Signed (favor + / against -)" if x == "signed" else "Positive-only (no negatives)",
        )
        if st.button("Parse with AI"):
            try:
                parsed = parse_free_text_rule(free_text, scoring_hint)
                tool = merge_ai_result(tool, parsed)
                st.session_state.editing_tool = tool
                st.success("AI rule added. Review below.")
            except Exception as exc:
                st.error(f"AI parse failed: {exc}")

        st.divider()
        st.subheader("Inputs")
        input_rows = tool_to_input_rows(tool)
        input_rows = st.data_editor(
            input_rows,
            num_rows="dynamic",
            column_config={
                "label": st.column_config.TextColumn("Label"),
                "type": st.column_config.SelectboxColumn("Type", options=INPUT_TYPES),
                "options_csv": st.column_config.TextColumn("Options (comma-separated)"),
            },
            key="inputs_editor",
        )
        tool["inputs"] = input_rows_to_tool(input_rows, tool.get("inputs", []))

        id_to_label, label_to_id = build_label_maps(tool["inputs"])
        label_options = list(id_to_label.values())

        st.divider()
        st.subheader("Scoring Rules")
        scoring_rules = tool.get("scoring_rules", [])
        if st.button("Add Scoring Rule"):
            scoring_rules.append(
                {
                    "input_id": "",
                    "favor_values": [],
                    "against_values": [],
                    "invert_favor": False,
                    "weight": 1,
                }
            )
            tool["scoring_rules"] = scoring_rules
            st.session_state.editing_tool = tool
            st.rerun()

        st.markdown("**Input / Favor / Against / Invert / Weight**")
        updated_scoring = []
        for idx, rule in enumerate(scoring_rules):
            cols = st.columns([3, 3, 3, 2, 2, 1])
            with cols[0]:
                selected_label = id_to_label.get(rule.get("input_id", ""), "")
                if label_options:
                    selected_label = st.selectbox(
                        "Input",
                        options=label_options,
                        index=label_options.index(selected_label) if selected_label in label_options else 0,
                        key=f"score_input_{idx}",
                    )
                    input_id = label_to_id.get(selected_label, "")
                else:
                    st.warning("Add inputs first.")
                    input_id = ""
            with cols[1]:
                options = get_input_options(tool["inputs"], input_id)
                default_favor = [v for v in rule.get("favor_values", []) if v in options]
                favor_values = st.multiselect(
                    "Favor values",
                    options=options,
                    default=default_favor,
                    key=f"score_favor_{idx}",
                )
            with cols[2]:
                options = get_input_options(tool["inputs"], input_id)
                default_against = [v for v in rule.get("against_values", []) if v in options]
                against_values = st.multiselect(
                    "Against values",
                    options=options,
                    default=default_against,
                    key=f"score_against_{idx}",
                )
            with cols[3]:
                invert_favor = st.checkbox(
                    "Invert",
                    value=bool(rule.get("invert_favor", False)),
                    key=f"score_invert_{idx}",
                )
            with cols[4]:
                weight = st.number_input(
                    "Weight",
                    min_value=1,
                    step=1,
                    value=int(rule.get("weight", 1) or 1),
                    key=f"score_weight_{idx}",
                )
            with cols[5]:
                if st.button("Remove", key=f"delete_score_{idx}"):
                    scoring_rules.pop(idx)
                    tool["scoring_rules"] = scoring_rules
                    st.session_state.editing_tool = tool
                    st.rerun()

            updated_scoring.append(
                {
                    "input_id": input_id,
                    "favor_values": favor_values,
                    "against_values": against_values,
                    "invert_favor": invert_favor,
                    "weight": weight,
                }
            )

        tool["scoring_rules"] = updated_scoring

        st.divider()
        st.subheader("Recommendation Rules")
        rules = tool.get("rules", [])
        if st.button("Add Recommendation Rule"):
            rules.append(
                {
                    "name": "",
                    "level": "info",
                    "message": "",
                    "condition_operator": "AND",
                    "conditions": [],
                }
            )
            tool["rules"] = rules
            st.session_state.editing_tool = tool
            st.rerun()

        updated_rules = []
        for ridx, rule in enumerate(rules):
            st.markdown(f"**Rule {ridx + 1}**")
            rcol1, rcol2 = st.columns([2, 1])
            with rcol1:
                name = st.text_input("Rule name", value=rule.get("name", ""), key=f"rule_name_{ridx}")
            with rcol2:
                level = st.selectbox(
                    "Level",
                    options=LEVELS,
                    index=LEVELS.index(rule.get("level", "info")),
                    key=f"rule_level_{ridx}",
                )
            condition_operator = st.selectbox(
                "Condition logic",
                options=["AND", "OR"],
                index=["AND", "OR"].index(safe_str(rule.get("condition_operator", "AND")).upper())
                if safe_str(rule.get("condition_operator", "AND")).upper() in ["AND", "OR"]
                else 0,
                key=f"rule_op_{ridx}",
            )
            message = st.text_area(
                "Message",
                value=rule.get("message", ""),
                key=f"rule_message_{ridx}",
            )

            st.markdown("**Conditions**")
            conditions = rule.get("conditions", [])
            if st.button("Add Condition", key=f"add_condition_{ridx}"):
                conditions.append({"input_id": "", "op": "equals", "value": ""})
                rules[ridx]["conditions"] = conditions
                tool["rules"] = rules
                st.session_state.editing_tool = tool
                st.rerun()

            updated_conditions = []
            for cidx, cond in enumerate(conditions):
                ccol0, ccol1, ccol2, ccol3 = st.columns([2, 3, 3, 1])
                with ccol0:
                    if cidx == 0:
                        join_with_previous = "AND"
                        st.text_input("Join", value="START", disabled=True, key=f"cond_join_{ridx}_{cidx}_label")
                    else:
                        join_with_previous = st.selectbox(
                            "Join",
                            options=["AND", "OR"],
                            index=["AND", "OR"].index(
                                safe_str(cond.get("join_with_previous", "AND")).upper()
                            )
                            if safe_str(cond.get("join_with_previous", "AND")).upper() in ["AND", "OR"]
                            else 0,
                            key=f"cond_join_{ridx}_{cidx}",
                        )

                with ccol1:
                    if label_options:
                        cond_label = id_to_label.get(cond.get("input_id", ""), "")
                        cond_label = st.selectbox(
                            "Input",
                            options=label_options,
                            index=label_options.index(cond_label) if cond_label in label_options else 0,
                            key=f"cond_input_{ridx}_{cidx}",
                        )
                        cond_input_id = label_to_id.get(cond_label, "")
                    else:
                        st.warning("Add inputs first.")
                        cond_input_id = ""

                with ccol2:
                    options = get_input_options(tool["inputs"], cond_input_id)
                    if options:
                        cond_value = st.selectbox(
                            "Value",
                            options=options,
                            index=options.index(cond.get("value")) if cond.get("value") in options else 0,
                            key=f"cond_value_{ridx}_{cidx}",
                        )
                    else:
                        cond_value = st.text_input(
                            "Value",
                            value=safe_str(cond.get("value")),
                            key=f"cond_value_{ridx}_{cidx}",
                        )

                with ccol3:
                    if st.button("Remove", key=f"remove_condition_{ridx}_{cidx}"):
                        conditions.pop(cidx)
                        rules[ridx]["conditions"] = conditions
                        tool["rules"] = rules
                        st.session_state.editing_tool = tool
                        st.rerun()

                updated_conditions.append(
                    {
                        "input_id": cond_input_id,
                        "op": "equals",
                        "value": cond_value,
                        "join_with_previous": join_with_previous if cidx > 0 else "AND",
                    }
                )

            if st.button("Delete Recommendation Rule", key=f"delete_rule_{ridx}"):
                rules.pop(ridx)
                tool["rules"] = rules
                st.session_state.editing_tool = tool
                st.rerun()

            updated_rules.append(
                {
                    "name": name,
                    "level": level,
                    "message": message,
                    "condition_operator": condition_operator,
                    "conditions": updated_conditions,
                }
            )

        tool["rules"] = updated_rules

        st.divider()
        st.subheader("Score-Based Recommendation")
        st.caption("Optional: show a recommendation based on total score thresholds.")
        scoring_recs = tool.get("scoring_recommendations", [])
        if st.button("Add Score Threshold"):
            scoring_recs.append({"min_score": 0, "level": "info", "message": ""})
            tool["scoring_recommendations"] = scoring_recs
            st.session_state.editing_tool = tool
            st.rerun()

        updated_scoring_recs = []
        for sidx, item in enumerate(scoring_recs):
            cols = st.columns([2, 2, 6, 1])
            with cols[0]:
                min_score = st.number_input(
                    "Min score",
                    value=int(item.get("min_score", 0) or 0),
                    step=1,
                    key=f"score_min_{sidx}",
                )
            with cols[1]:
                level = st.selectbox(
                    "Level",
                    options=LEVELS,
                    index=LEVELS.index(item.get("level", "info")),
                    key=f"score_level_{sidx}",
                )
            with cols[2]:
                message = st.text_input(
                    "Message",
                    value=item.get("message", ""),
                    key=f"score_msg_{sidx}",
                )
            with cols[3]:
                if st.button("Remove", key=f"score_remove_{sidx}"):
                    scoring_recs.pop(sidx)
                    tool["scoring_recommendations"] = scoring_recs
                    st.session_state.editing_tool = tool
                    st.rerun()

            conditions = item.get("conditions", [])
            if st.button("Add Condition", key=f"score_add_cond_{sidx}"):
                conditions.append({"input_id": "", "op": "equals", "value": ""})
                item["conditions"] = conditions
                tool["scoring_recommendations"] = scoring_recs
                st.session_state.editing_tool = tool
                st.rerun()

            updated_conditions = []
            for cidx, cond in enumerate(conditions):
                ccol1, ccol2, ccol3 = st.columns([3, 3, 1])
                with ccol1:
                    if label_options:
                        cond_label = id_to_label.get(cond.get("input_id", ""), "")
                        cond_label = st.selectbox(
                            "Input",
                            options=label_options,
                            index=label_options.index(cond_label) if cond_label in label_options else 0,
                            key=f"score_cond_input_{sidx}_{cidx}",
                        )
                        cond_input_id = label_to_id.get(cond_label, "")
                    else:
                        st.warning("Add inputs first.")
                        cond_input_id = ""
                with ccol2:
                    options = get_input_options(tool["inputs"], cond_input_id)
                    if options:
                        cond_value = st.selectbox(
                            "Value",
                            options=options,
                            index=options.index(cond.get("value")) if cond.get("value") in options else 0,
                            key=f"score_cond_value_{sidx}_{cidx}",
                        )
                    else:
                        cond_value = st.text_input(
                            "Value",
                            value=safe_str(cond.get("value")),
                            key=f"score_cond_value_{sidx}_{cidx}",
                        )
                with ccol3:
                    if st.button("Remove", key=f"score_cond_remove_{sidx}_{cidx}"):
                        conditions.pop(cidx)
                        item["conditions"] = conditions
                        tool["scoring_recommendations"] = scoring_recs
                        st.session_state.editing_tool = tool
                        st.rerun()

                updated_conditions.append(
                    {"input_id": cond_input_id, "op": "equals", "value": cond_value}
                )

            updated_scoring_recs.append(
                {
                    "min_score": int(min_score),
                    "level": level,
                    "message": message,
                    "conditions": updated_conditions,
                }
            )

        tool["scoring_recommendations"] = updated_scoring_recs

        st.divider()
        if st.button("Save Tool"):
            ok, message, github_path = save_tool_to_github(tool)
            if github_path:
                tool["github_path"] = github_path
            st.session_state.tools_data["tools"][st.session_state.selected_tool_id] = deepcopy(tool)
            save_tools(st.session_state.tools_data)
            st.success("Tool saved.")
            if ok:
                st.success(message)
            else:
                st.warning(message)

        st.divider()
        st.subheader("Delete Calculator")
        confirm_delete = st.checkbox("I understand this will delete the calculator from GitHub")
        if st.button("Delete from GitHub"):
            if not confirm_delete:
                st.warning("Please confirm deletion first.")
            else:
                ok, message = delete_tool_from_github(tool)
                if ok:
                    st.success(message)
                    current_id = st.session_state.selected_tool_id
                    if current_id in st.session_state.tools_data.get("tools", {}):
                        del st.session_state.tools_data["tools"][current_id]
                        save_tools(st.session_state.tools_data)
                        remaining_ids = list(st.session_state.tools_data.get("tools", {}).keys())
                        st.session_state.selected_tool_id = remaining_ids[0] if remaining_ids else None
                        st.session_state.editing_tool = None
                        st.session_state.editing_tool_id = None
                        st.rerun()
                else:
                    st.warning(message)
        st.download_button(
            "Download Tool JSON",
            data=json.dumps(tool, indent=2),
            file_name=f"{safe_str(tool.get('name','tool')).replace(' ', '_').lower() or 'tool'}.json",
            mime="application/json",
        )

    with tabs[1]:
        st.subheader(tool.get("name", "Tool Preview"))
        if tool.get("description"):
            st.write(tool.get("description"))

        preview_values = st.session_state.preview_values.get(st.session_state.selected_tool_id, {})

        for item in tool.get("inputs", []):
            input_id = item.get("id")
            label = item.get("label", input_id)
            input_type = item.get("type", "select")
            key = f"preview_{st.session_state.selected_tool_id}_{input_id}"

            if input_type == "select":
                options = item.get("options", [])
                if not options:
                    options = [""]
                default = preview_values.get(input_id, options[0])
                value = st.selectbox(label, options, index=options.index(default) if default in options else 0, key=key)
            elif input_type == "number":
                default = preview_values.get(input_id, 0.0)
                value = st.number_input(label, value=float(default), key=key)
            else:
                default = preview_values.get(input_id, "")
                value = st.text_input(label, value=str(default), key=key)

            preview_values[input_id] = value

        st.session_state.preview_values[st.session_state.selected_tool_id] = preview_values

        st.divider()
        st.subheader("Results")
        level, message = evaluate_rules(tool, preview_values)
        if level and message:
            render_message(level, message)

        if tool.get("scoring_rules"):
            plus, minus, total = compute_scores(tool, preview_values)
            score_reco = evaluate_score_recommendation(tool, preview_values, total)
            if score_reco:
                render_message(score_reco.get("level", "info"), score_reco.get("message", ""))
                st.write(f"**Score:** {total}")
            else:
                if tool.get("scoring_mode", "signed") == "signed":
                    st.write(f"✅ **Factors favoring intervention:** {plus}")
                    st.write(f"❌ **Factors NOT favoring intervention:** {minus}")
                else:
                    st.write(f"**Score:** {total}")

        if st.checkbox("Show decision tree", key="show_decision_tree"):
            id_to_label, _ = build_label_maps(tool.get("inputs", []))
            st.graphviz_chart(build_decision_tree_graph(tool, id_to_label))


if __name__ == "__main__":
    main()
