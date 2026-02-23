import base64
import json
import hashlib
import mimetypes
import os
import re
import uuid
from copy import deepcopy
from typing import Dict, List, Tuple
from urllib import error, request

import streamlit as st

DATA_PATH = os.path.join("data", "tools.json")
GITHUB_REPO = "ayushbalaji-dotcom/homepagev2"
GITHUB_BRANCH = "main"
GITHUB_CALCULATORS_DIR = "calculators"
GITHUB_GUIDELINE_DIR = GITHUB_CALCULATORS_DIR

DEFAULT_TOOL = {
    "name": "New Tool",
    "description": "",
    "inputs": [
        {"id": "example_yes_no", "label": "Example Yes/No?", "type": "select", "options": ["Yes", "No", "Unknown"]}
    ],
    "scoring_rules": [
        {
            "input_id": "example_yes_no",
            "favor_values": ["Yes"],
            "against_values": ["No"],
            "invert_favor": False,
            "weight": 1,
        }
    ],
    "rules": [
        {
            "name": "Example Rule",
            "level": "info",
            "message": "Example: Rule matched",
            "conditions": [
                {"input_id": "example_yes_no", "op": "equals", "value": "Yes"}
            ],
        }
    ],
    "fallback": {"level": "warning", "message": "No rules matched."},
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

def get_github_token():
    return st.secrets.get("github_token") or os.environ.get("GITHUB_TOKEN")


def github_request(method: str, url: str, token: str, payload: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "calculator-builder",
        "Authorization": f"Bearer {token}",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, method=method, headers=headers, data=data)
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_tools():
    if not os.path.exists(DATA_PATH):
        return {"tools": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tools(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ensure_state():
    if "tools_data" not in st.session_state:
        st.session_state.tools_data = load_tools()
        tools = st.session_state.tools_data.setdefault("tools", {})
        if "tricuspid_repair" not in tools:
            tools["tricuspid_repair"] = deepcopy(TRICUSPID_TOOL)
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


def build_guideline_filename(tool_id: str, tool_name: str, extension: str) -> str:
    base = slugify(tool_name) or "guideline"
    ext = (extension or "").lstrip(".") or "png"
    return f"guideline_{tool_id}_{base}.{ext}"


def save_guideline_image_to_github(image_bytes: bytes, filename: str, mime: str):
    token = get_github_token()
    if not token:
        return False, "Missing GitHub token. Add github_token to Streamlit secrets."

    path = f"{GITHUB_GUIDELINE_DIR}/{filename}"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

    existing_sha = None
    try:
        existing = github_request("GET", f"{url}?ref={GITHUB_BRANCH}", token)
        existing_sha = existing.get("sha")
    except error.HTTPError as exc:
        if exc.code != 404:
            return False, f"GitHub lookup failed: {exc}"

    payload = {
        "message": f"Add/Update guideline image {filename}",
        "content": base64.b64encode(image_bytes).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    try:
        github_request("PUT", url, token, payload)
        return True, {
            "github_path": path,
            "raw_url": f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{path}",
            "mime": mime,
        }
    except error.HTTPError as exc:
        return False, f"GitHub save failed: {exc}"


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

def tool_to_input_rows(tool):
    rows = []
    for item in tool.get("inputs", []):
        rows.append(
            {
                "id": item.get("id", ""),
                "label": item.get("label", ""),
                "type": item.get("type", "select"),
                "options_csv": ", ".join(item.get("options", [])),
            }
        )
    return rows


def input_rows_to_tool(rows):
    inputs = []
    for row in rows:
        if not row.get("id"):
            continue
        inputs.append(
            {
                "id": safe_str(row.get("id")),
                "label": safe_str(row.get("label", "")),
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
    def condition_match(cond):
        input_id = cond.get("input_id")
        expected = cond.get("value")
        op = safe_str(cond.get("op")) or "equals"
        actual = values.get(input_id)
        if op == "not_equals":
            return actual != expected
        return actual == expected

    def evaluate_condition_expression(rule):
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
        group_results = []

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

    if best_match:
        return best_match.get("level", "info"), best_match.get("message", "")

    fallback = tool.get("fallback", {"level": "warning", "message": "No rules matched."})
    return fallback.get("level", "warning"), fallback.get("message", "No rules matched.")


def compute_scores(tool, values):
    plus = 0
    minus = 0
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
        elif score == -1:
            minus += weight
    return plus, minus


def build_decision_tree_graph(tool: Dict, id_to_label: Dict[str, str], values: Dict | None = None) -> str:
    values = values or {}

    def condition_match(cond: Dict) -> bool:
        input_id = cond.get("input_id")
        expected = cond.get("value")
        actual = values.get(input_id)
        op = safe_str(cond.get("op")) or "equals"
        if op == "not_equals":
            return actual != expected
        return actual == expected

    lines = [
        "digraph DecisionTree {",
        'rankdir=LR;',
        'node [shape=box, style="rounded,filled", color="gray35", fillcolor="white"];',
    ]
    lines.append('start [label="Start", shape=oval, fillcolor="white"];')
    for ridx, rule in enumerate(tool.get("rules", [])):
        conditions = rule.get("conditions", [])
        rule_node = f"rule_{ridx}"
        rule_label = safe_str(rule.get("name")) or f"Rule {ridx + 1}"
        rule_match = all(condition_match(c) for c in conditions) if conditions else False
        rule_attrs = 'fillcolor="white"'
        if rule_match:
            rule_attrs = 'fillcolor="lightyellow", color="goldenrod"'
        lines.append(f'{rule_node} [label="{rule_label}", {rule_attrs}];')
        lines.append(f"start -> {rule_node};")

        prev_node = rule_node
        for cidx, cond in enumerate(conditions):
            cond_node = f"rule_{ridx}_cond_{cidx}"
            input_label = id_to_label.get(cond.get("input_id", ""), cond.get("input_id", ""))
            value = safe_str(cond.get("value"))
            op = safe_str(cond.get("op")) or "equals"
            operator_label = "!=" if op == "not_equals" else "="
            cond_label = f"{input_label} {operator_label} {value}".replace('"', "'")
            matched = condition_match(cond)
            cond_attrs = 'fillcolor="white"'
            if values and matched:
                cond_attrs = 'fillcolor="palegreen", color="green"'
            lines.append(f'{cond_node} [label="{cond_label}", {cond_attrs}];')
            lines.append(f"{prev_node} -> {cond_node};")
            prev_node = cond_node

        out_node = f"rule_{ridx}_out"
        msg = safe_str(rule.get("message")) or "Recommendation"
        msg = msg.replace('"', "'")
        out_attrs = 'fillcolor="white"'
        if rule_match:
            out_attrs = 'fillcolor="lightblue", color="dodgerblue4"'
        lines.append(f'{out_node} [shape=note, label="{msg}", {out_attrs}];')
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

        st.divider()
        st.subheader("Guideline Image")
        st.caption("Optional. This image will be shown at the bottom of the guideline table.")
        image_upload = st.file_uploader("Upload guideline image", type=["png", "jpg", "jpeg", "gif"])
        if "guideline_upload_keys" not in st.session_state:
            st.session_state.guideline_upload_keys = {}
        if image_upload is not None:
            image_bytes = image_upload.getvalue()
            mime = image_upload.type or "image/png"
            file_ext = os.path.splitext(image_upload.name or "")[1].lstrip(".")
            if not file_ext:
                guessed_ext = mimetypes.guess_extension(mime) or ".png"
                file_ext = guessed_ext.lstrip(".")
            image_hash = hashlib.md5(image_bytes).hexdigest()
            upload_key = f"{st.session_state.selected_tool_id}:{image_hash}"
            if st.session_state.guideline_upload_keys.get(st.session_state.selected_tool_id) != upload_key:
                filename = build_guideline_filename(
                    st.session_state.selected_tool_id, tool.get("name", ""), file_ext
                )
                ok, result = save_guideline_image_to_github(image_bytes, filename, mime)
                if ok:
                    tool["guideline_image"] = result
                    st.session_state.guideline_upload_keys[st.session_state.selected_tool_id] = upload_key
                    st.success("Image uploaded to GitHub.")
                else:
                    st.warning(result)
            else:
                st.caption("Image already uploaded.")
            st.image(image_bytes, use_container_width=True)
        elif tool.get("guideline_image"):
            image_to_show = tool.get("guideline_image")
            if isinstance(image_to_show, dict):
                image_to_show = image_to_show.get("raw_url") or image_to_show.get("url")
            if image_to_show:
                st.image(image_to_show, use_container_width=True)

        st.divider()
        st.subheader("Inputs")
        inputs = ensure_input_ids(tool.get("inputs", []))
        if st.button("Add Input"):
            inputs.append(
                {
                    "id": "",
                    "label": "",
                    "type": "select",
                    "options": [],
                }
            )
            st.rerun()

        updated_inputs = []
        for idx, item in enumerate(inputs):
            label_value = safe_str(item.get("label"))
            with st.expander(label_value or f"Input {idx + 1}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    label_value = st.text_input(
                        "Label",
                        value=label_value,
                        key=f"input_label_{idx}",
                    )
                    input_type = st.selectbox(
                        "Type",
                        options=INPUT_TYPES,
                        index=INPUT_TYPES.index(item.get("type", "select")),
                        key=f"input_type_{idx}",
                    )
                with col2:
                    auto_key = f"input_auto_{idx}"
                    if auto_key not in st.session_state:
                        st.session_state[auto_key] = not safe_str(item.get("id"))
                    auto_id = st.checkbox(
                        "Auto-generate ID from label",
                        value=st.session_state[auto_key],
                        key=auto_key,
                    )
                    if auto_id:
                        input_id = slugify(label_value)
                        st.text_input("ID", value=input_id, disabled=True, key=f"input_id_{idx}")
                    else:
                        input_id = st.text_input(
                            "ID",
                            value=safe_str(item.get("id")),
                            key=f"input_id_{idx}",
                        )

                options = item.get("options", [])
                if input_type == "select":
                    options_csv = st.text_input(
                        "Options (comma-separated)",
                        value=", ".join(options),
                        key=f"input_opts_{idx}",
                    )
                    options = normalize_options(options_csv)
                else:
                    st.caption("Options apply to select inputs only.")
                    options = []

                if st.button("Delete Input", key=f"delete_input_{idx}"):
                    inputs.pop(idx)
                    st.rerun()

                updated_inputs.append(
                    {
                        "id": safe_str(input_id),
                        "label": safe_str(label_value),
                        "type": input_type,
                        "options": options,
                    }
                )

        tool["inputs"] = updated_inputs

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
            st.rerun()

        updated_scoring = []
        for idx, rule in enumerate(scoring_rules):
            with st.expander(f"Scoring Rule {idx + 1}", expanded=True):
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
                    st.warning("Add inputs first to define scoring rules.")
                    input_id = ""

                options = get_input_options(tool["inputs"], input_id)
                favor_values = st.multiselect(
                    "Favor values",
                    options=options,
                    default=rule.get("favor_values", []),
                    key=f"score_favor_{idx}",
                )
                against_values = st.multiselect(
                    "Against values",
                    options=options,
                    default=rule.get("against_values", []),
                    key=f"score_against_{idx}",
                )
                invert_favor = st.checkbox(
                    "Invert (yes counts against)",
                    value=bool(rule.get("invert_favor", False)),
                    key=f"score_invert_{idx}",
                )
                weight = st.number_input(
                    "Weight",
                    min_value=1,
                    step=1,
                    value=int(rule.get("weight", 1) or 1),
                    key=f"score_weight_{idx}",
                )

                if st.button("Delete Scoring Rule", key=f"delete_score_{idx}"):
                    scoring_rules.pop(idx)
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
                    "conditions": [],
                }
            )
            st.rerun()

        updated_rules = []
        for ridx, rule in enumerate(rules):
            with st.expander(rule.get("name") or f"Rule {ridx + 1}", expanded=True):
                name = st.text_input("Rule name", value=rule.get("name", ""), key=f"rule_name_{ridx}")
                level = st.selectbox(
                    "Level",
                    options=LEVELS,
                    index=LEVELS.index(rule.get("level", "info")),
                    key=f"rule_level_{ridx}",
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
                                key=f"cond_input_{ridx}_{cidx}",
                            )
                            cond_input_id = label_to_id.get(cond_label, "")
                        else:
                            st.warning("Add inputs first to define conditions.")
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
                            st.rerun()

                    updated_conditions.append(
                        {"input_id": cond_input_id, "op": "equals", "value": cond_value}
                    )

                if st.button("Delete Recommendation Rule", key=f"delete_rule_{ridx}"):
                    rules.pop(ridx)
                    st.rerun()

                updated_rules.append(
                    {
                        "name": name,
                        "level": level,
                        "message": message,
                        "conditions": updated_conditions,
                    }
                )

        tool["rules"] = updated_rules

        st.subheader("Fallback Message")
        fallback_level = st.selectbox("Fallback level", LEVELS, index=LEVELS.index(tool.get("fallback", {}).get("level", "warning")))
        fallback_message = st.text_input("Fallback message", value=tool.get("fallback", {}).get("message", "No rules matched."))
        tool["fallback"] = {"level": fallback_level, "message": fallback_message}

        st.divider()
        if st.button("Save Tool"):
            st.session_state.tools_data["tools"][st.session_state.selected_tool_id] = deepcopy(tool)
            save_tools(st.session_state.tools_data)
            st.success("Tool saved.")
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
        render_message(level, message)

        plus, minus = compute_scores(tool, preview_values)
        st.write(f"✅ **Factors favoring intervention:** {plus}")
        st.write(f"❌ **Factors NOT favoring intervention:** {minus}")

        if st.checkbox("Show decision tree", key=f"show_decision_tree_{st.session_state.selected_tool_id}"):
            id_to_label, _ = build_label_maps(tool.get("inputs", []))
            st.graphviz_chart(build_decision_tree_graph(tool, id_to_label, preview_values))

        if tool.get("guideline_image"):
            st.divider()
            st.subheader("Guideline Table Image")
            image_to_show = tool.get("guideline_image")
            if isinstance(image_to_show, dict):
                image_to_show = image_to_show.get("raw_url") or image_to_show.get("url")
            if image_to_show:
                st.image(image_to_show, use_container_width=True)


if __name__ == "__main__":
    main()
