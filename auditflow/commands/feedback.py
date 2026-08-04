from __future__ import annotations

import argparse
import html
import re
import unicodedata
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any

from auditflow.localization import (
    load_messages,
    message,
    read_project_language,
    render_localized_template,
)
from auditflow.template_utils import render_template

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required. Install it with: pip install pyyaml") from exc


EN_MESSAGES = load_messages("en")
QUESTIONS: list[dict[str, str]] = message(EN_MESSAGES, "feedback.questions")
OPEN_QUESTIONS: list[dict[str, str]] = message(EN_MESSAGES, "feedback.open_questions")
SCORE_GUIDANCE = message(EN_MESSAGES, "feedback.score_guidance")


def load_yaml(path: Path, default: Any | None = None) -> Any:
    if default is None:
        default = {}

    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or default


def write_yaml(path: Path, data: Any) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def find_project_root(start_paths: list[Path]) -> Path:
    for start in start_paths:
        current = start.resolve()

        while current != current.parent:
            if (current / "initial_data.yml").exists() and (current / "00_admin" / "stakeholders.yml").exists():
                return current

            current = current.parent

    raise FileNotFoundError(
        "Could not find audit project root. Expected initial_data.yml in the root "
        "and 00_admin/stakeholders.yml."
    )


def slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    return slug or fallback


def qmd_escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def audit_title(initial_data: dict[str, Any], language: str = "en") -> str:
    default_title = message(load_messages(language), "feedback.audit_default")
    audit = initial_data.get("audit", {})
    if isinstance(audit, dict):
        return str(audit.get("title") or audit.get("id") or default_title)
    return default_title


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def first_non_empty(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = text(item.get(key))
        if value:
            return value

    return ""


def person_name(person: dict[str, Any]) -> str:
    return first_non_empty(person, "name", "full_name", "person")


def person_role(person: dict[str, Any]) -> str:
    return first_non_empty(person, "role", "title", "position", "job_title")


def person_email(person: dict[str, Any]) -> str:
    return first_non_empty(person, "email", "email_address", "mail")


def normalize_recipient(person: dict[str, Any], source: str) -> dict[str, str]:
    return {
        "name": person_name(person),
        "role": person_role(person),
        "email": person_email(person),
        "source": source,
    }


def recipient_key(recipient: dict[str, str]) -> str:
    email = recipient.get("email", "").strip().lower()
    if email:
        return f"email:{email}"

    return f"name:{recipient.get('name', '').strip().lower()}"


def add_recipient_once(
    recipients: list[dict[str, str]],
    seen: set[str],
    recipient: dict[str, str],
) -> None:
    if not recipient.get("name"):
        return

    key = recipient_key(recipient)
    if key in seen:
        return

    seen.add(key)
    recipients.append(recipient)


def recipients_from_stakeholders(
    stakeholders: dict[str, Any],
    include_sponsor: bool = False,
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()

    if include_sponsor:
        sponsor = stakeholders.get("sponsor")
        if isinstance(sponsor, dict):
            add_recipient_once(result, seen, normalize_recipient(sponsor, "sponsor"))

    for person in stakeholders.get("auditees", []) or []:
        if not isinstance(person, dict):
            continue

        add_recipient_once(result, seen, normalize_recipient(person, "auditee"))

    if result:
        return result

    for person in stakeholders.get("report_recipients", []) or []:
        if not isinstance(person, dict):
            continue

        add_recipient_once(result, seen, normalize_recipient(person, "report_recipient"))

    return result


def request_subject(audit_name: str, language: str = "en") -> str:
    template = message(load_messages(language), "feedback.request_subject")
    return str(template).format(audit_name=audit_name)


def format_questions_for_request(
    questions: list[dict[str, str]],
    *,
    score_label: str = "Score",
    comment_label: str = "Comment",
) -> str:
    lines: list[str] = []

    for index, item in enumerate(questions, start=1):
        lines.extend(
            [
                f"{index}. {item['question']}",
                f"{score_label}: ",
                f"{comment_label}: ",
                "",
            ]
        )

    return "\n".join(lines).rstrip()


def format_open_questions_for_request(
    open_questions: list[dict[str, str]],
    *,
    answer_label: str = "Answer",
) -> str:
    lines: list[str] = []

    for index, item in enumerate(open_questions, start=1):
        lines.extend(
            [
                f"{index}. {item['question']}",
                f"{answer_label}: ",
                "",
            ]
        )

    return "\n".join(lines).rstrip()


def render_plain_text_request(
    *,
    recipient: dict[str, str],
    audit_name: str,
    response_due_date: str,
    language: str = "en",
) -> str:
    messages = load_messages(language)
    questions = message(messages, "feedback.questions")
    open_questions = message(messages, "feedback.open_questions")
    response_due_date_line = ""
    if response_due_date:
        response_due_date_line = str(
            message(messages, "feedback.requested_response_date")
        ).format(date=response_due_date)

    recipient_role = recipient.get("role", "")
    recipient_role_suffix = f", {recipient_role}" if recipient_role else ""

    return render_localized_template(
        "feedback_request.txt",
        {
            "audit_name": audit_name,
            "recipient_name": recipient["name"],
            "recipient_role": recipient.get("role", ""),
            "recipient_role_suffix": recipient_role_suffix,
            "response_due_date_line": response_due_date_line,
            "score_guidance": message(messages, "feedback.score_guidance"),
            "questions_block": format_questions_for_request(
                questions,
                score_label=message(messages, "feedback.score"),
                comment_label=message(messages, "feedback.comment"),
            ),
            "open_questions_block": format_open_questions_for_request(
                open_questions,
                answer_label=message(messages, "feedback.answer"),
            ),
        },
        language,
    ).strip() + "\n"


def yaml_double_quote_escape(value: Any) -> str:
    return str(value if value is not None else "").replace('"', '\\\"')


def format_scores_for_response_template(questions: list[dict[str, str]]) -> str:
    lines: list[str] = []

    for item in questions:
        question = yaml_double_quote_escape(item["question"])
        lines.extend(
            [
                f'  - id: {item["id"]}',
                f'    question: "{question}"',
                "    score: null",
                '    comment: ""',
            ]
        )

    return "\n".join(lines)


def format_open_feedback_for_response_template(open_questions: list[dict[str, str]]) -> str:
    lines: list[str] = []

    for item in open_questions:
        question = yaml_double_quote_escape(item["question"])
        lines.extend(
            [
                f'  - id: {item["id"]}',
                f'    question: "{question}"',
                '    answer: ""',
            ]
        )

    return "\n".join(lines)


def response_template(
    *,
    recipient: dict[str, str],
    audit_name: str,
    request_file: str,
    questions: list[dict[str, str]] = QUESTIONS,
    open_questions: list[dict[str, str]] = OPEN_QUESTIONS,
) -> dict[str, Any]:
    rendered = render_template(
        "feedback_response.yml",
        {
            "audit_name": yaml_double_quote_escape(audit_name),
            "recipient_name": yaml_double_quote_escape(recipient.get("name", "")),
            "recipient_role": yaml_double_quote_escape(recipient.get("role", "")),
            "recipient_email": yaml_double_quote_escape(recipient.get("email", "")),
            "recipient_source": yaml_double_quote_escape(recipient.get("source", "")),
            "request_file": yaml_double_quote_escape(request_file.replace(chr(92), "/")),
            "scores_block": format_scores_for_response_template(questions),
            "open_feedback_block": format_open_feedback_for_response_template(open_questions),
        },
    )
    return yaml.safe_load(rendered) or {}


def response_is_filled(path: Path) -> bool:
    data = load_yaml(path, default={})
    if not isinstance(data, dict):
        return False

    response = data.get("response", {})
    if isinstance(response, dict) and response.get("received"):
        return True

    scores = data.get("scores", [])
    if isinstance(scores, list):
        for item in scores:
            if isinstance(item, dict) and (item.get("score") not in (None, "") or item.get("comment")):
                return True

    open_feedback = data.get("open_feedback", [])
    if isinstance(open_feedback, list):
        for item in open_feedback:
            if isinstance(item, dict) and item.get("answer"):
                return True

    return False


def create_requests(
    *,
    project_root: Path,
    include_sponsor: bool,
    response_due_date: str,
    overwrite_requests: bool,
    reset_response_templates: bool,
) -> None:
    language = read_project_language(project_root)
    messages = load_messages(language)
    questions = message(messages, "feedback.questions")
    open_questions = message(messages, "feedback.open_questions")
    initial_data = load_yaml(project_root / "initial_data.yml", default={})
    stakeholders = load_yaml(project_root / "00_admin" / "stakeholders.yml", default={})

    audit_name = audit_title(initial_data, language=language)
    recipients = recipients_from_stakeholders(stakeholders, include_sponsor=include_sponsor)

    if not recipients:
        raise SystemExit("No recipients found in 00_admin/stakeholders.yml.")

    feedback_dir = project_root / "08_feedback"
    request_dir = feedback_dir / "request"
    response_dir = feedback_dir / "response"
    original_dir = response_dir / "original"

    request_dir.mkdir(parents=True, exist_ok=True)
    response_dir.mkdir(parents=True, exist_ok=True)
    original_dir.mkdir(parents=True, exist_ok=True)

    for index, recipient in enumerate(recipients, start=1):
        slug = slugify(recipient["name"], fallback=f"recipient_{index:02d}")

        request_path = request_dir / f"{index:02d}_{slug}_request.txt"
        response_path = response_dir / f"{index:02d}_{slug}_response.yml"

        if request_path.exists() and not overwrite_requests:
            raise FileExistsError(f"{request_path} already exists. Use --overwrite to replace request files.")

        request_text = render_plain_text_request(
            recipient=recipient,
            audit_name=audit_name,
            response_due_date=response_due_date,
            language=language,
        )
        request_path.write_text(request_text, encoding="utf-8")

        template = response_template(
            recipient=recipient,
            audit_name=audit_name,
            request_file=request_path.relative_to(feedback_dir).as_posix(),
            questions=questions,
            open_questions=open_questions,
        )

        if response_path.exists():
            if reset_response_templates:
                write_yaml(response_path, template)
            elif response_is_filled(response_path):
                print(f"Response template kept because it appears filled: {response_path}")
            else:
                # Keep an existing blank template to avoid unnecessary churn.
                print(f"Response template already exists and was kept: {response_path}")
        else:
            write_yaml(response_path, template)

    readme_path = feedback_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            render_localized_template(
                "feedback_readme.md",
                {
                    "generated_date": date.today().isoformat(),
                    "audit_name": audit_name,
                },
                language,
            ),
            encoding="utf-8",
        )

    print(f"Generated {len(recipients)} feedback request(s).")
    print(f"Feedback directory: {feedback_dir}")
    print(f"Request directory: {request_dir}")
    print(f"Response directory: {response_dir}")


def parse_score(value: Any) -> float | None:
    if value in (None, ""):
        return None

    text = str(value).strip().upper()
    if text == "N/A":
        return None

    try:
        numeric = float(text)
    except ValueError:
        return None

    if numeric < 1 or numeric > 5:
        return None

    return numeric


def score_label(value: Any) -> str:
    numeric = parse_score(value)
    if numeric is None:
        return "" if value in (None, "") else str(value)

    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def response_has_entered_content(data: dict[str, Any]) -> bool:
    """Return True if the response template contains any entered feedback.

    The auditor should not have to remember to flip response.received to true.
    If scores, comments, open answers, response date, original response file, or notes
    are entered, the response is treated as received for summary purposes.
    """
    response = data.get("response", {})
    if isinstance(response, dict):
        for key in ["received_date", "original_response_file", "notes"]:
            if str(response.get(key, "") or "").strip():
                return True

    scores = data.get("scores", [])
    if isinstance(scores, list):
        for item in scores:
            if not isinstance(item, dict):
                continue

            if item.get("score") not in (None, ""):
                return True

            if str(item.get("comment", "") or "").strip():
                return True

    open_feedback = data.get("open_feedback", [])
    if isinstance(open_feedback, list):
        for item in open_feedback:
            if isinstance(item, dict) and str(item.get("answer", "") or "").strip():
                return True

    return False


def response_received_explicit(data: dict[str, Any]) -> bool:
    response = data.get("response", {})
    if not isinstance(response, dict):
        return False

    return bool(response.get("received"))


def response_received(data: dict[str, Any]) -> bool:
    """Effective response status used by the summary.

    A response is received if it is explicitly marked as received OR if the
    auditor has entered scores/comments/open answers. This prevents filled
    templates from being ignored just because response.received remained false.
    """
    return response_received_explicit(data) or response_has_entered_content(data)


def response_status_label(
    data: dict[str, Any],
    messages: dict[str, Any] | None = None,
) -> str:
    messages = messages or EN_MESSAGES
    if response_received_explicit(data):
        return message(messages, "feedback.received")

    if response_has_entered_content(data):
        return message(messages, "feedback.received_inferred")

    return message(messages, "feedback.not_received")


def load_response_files(feedback_dir: Path) -> list[dict[str, Any]]:
    response_dir = feedback_dir / "response"
    responses: list[dict[str, Any]] = []

    if not response_dir.exists():
        return responses

    for path in sorted(response_dir.glob("*_response.yml")):
        data = load_yaml(path, default={})
        if isinstance(data, dict):
            data["_path"] = path
            responses.append(data)

    return responses


def response_average(data: dict[str, Any]) -> float | None:
    scores = data.get("scores", [])
    if not isinstance(scores, list):
        return None

    values = [
        parse_score(item.get("score"))
        for item in scores
        if isinstance(item, dict)
    ]
    values = [value for value in values if value is not None]

    if not values:
        return None

    return round(mean(values), 2)


def format_avg(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def build_summary_qmd(
    responses: list[dict[str, Any]],
    language: str = "en",
) -> str:
    messages = load_messages(language)
    questions = message(messages, "feedback.questions")
    yes = message(messages, "feedback.yes")
    no = message(messages, "feedback.no")
    audit_title_value = ""
    if responses:
        audit = responses[0].get("audit", {})
        if isinstance(audit, dict):
            audit_title_value = str(audit.get("title", ""))

    sent_count = len(responses)
    received_count = sum(1 for item in responses if response_received(item))
    missing_count = sent_count - received_count

    all_numeric_scores: list[float] = []
    for data in responses:
        if not response_received(data):
            continue

        for score_item in data.get("scores", []) or []:
            if isinstance(score_item, dict):
                score = parse_score(score_item.get("score"))
                if score is not None:
                    all_numeric_scores.append(score)

    overall_average = round(mean(all_numeric_scores), 2) if all_numeric_scores else None

    recipient_rows = []
    for data in responses:
        recipient = data.get("recipient", {}) if isinstance(data.get("recipient"), dict) else {}
        response = data.get("response", {}) if isinstance(data.get("response"), dict) else {}
        request = data.get("request", {}) if isinstance(data.get("request"), dict) else {}

        status = response_status_label(data, messages)

        recipient_rows.append(
            "| "
            + " | ".join(
                [
                    qmd_escape(recipient.get("name", "")),
                    qmd_escape(recipient.get("role", "")),
                    qmd_escape(recipient.get("email", "")),
                    qmd_escape(yes if request.get("sent") else no),
                    qmd_escape(status),
                    qmd_escape(response.get("received_date", "")),
                    qmd_escape(format_avg(response_average(data)) if response_received(data) else "—"),
                    qmd_escape(response.get("original_response_file", "")),
                ]
            )
            + " |"
        )

    question_rows = []
    for question in questions:
        values: list[float] = []
        comments: list[str] = []

        for data in responses:
            if not response_received(data):
                continue

            for item in data.get("scores", []) or []:
                if not isinstance(item, dict) or item.get("id") != question["id"]:
                    continue

                score = parse_score(item.get("score"))
                if score is not None:
                    values.append(score)

                comment = str(item.get("comment", "") or "").strip()
                if comment:
                    recipient = data.get("recipient", {}) if isinstance(data.get("recipient"), dict) else {}
                    comments.append(f"{recipient.get('name', '')}: {comment}")

        question_rows.append(
            "| "
            + " | ".join(
                [
                    qmd_escape(question["id"]),
                    qmd_escape(question["question"]),
                    str(len(values)),
                    qmd_escape(format_avg(round(mean(values), 2) if values else None)),
                    qmd_escape("; ".join(comments)),
                ]
            )
            + " |"
        )

    detailed_rows = []
    for data in responses:
        recipient = data.get("recipient", {}) if isinstance(data.get("recipient"), dict) else {}
        name = recipient.get("name", "")
        received = response_received(data)

        for item in data.get("scores", []) or []:
            if not isinstance(item, dict):
                continue

            detailed_rows.append(
                "| "
                + " | ".join(
                    [
                        qmd_escape(name),
                        qmd_escape(yes if received else no),
                        qmd_escape(item.get("id", "")),
                        qmd_escape(item.get("question", "")),
                        qmd_escape(score_label(item.get("score"))),
                        qmd_escape(item.get("comment", "")),
                    ]
                )
                + " |"
            )

    open_feedback_blocks = []
    for data in responses:
        if not response_received(data):
            continue

        recipient = data.get("recipient", {}) if isinstance(data.get("recipient"), dict) else {}
        name = recipient.get("name", "")
        answers = data.get("open_feedback", []) or []

        rendered_answers = []
        for item in answers:
            if not isinstance(item, dict):
                continue

            answer = str(item.get("answer", "") or "").strip()
            if not answer:
                continue

            rendered_answers.append(
                f"""
**{qmd_escape(item.get("question", ""))}**

{answer}
"""
            )

        if rendered_answers:
            open_feedback_blocks.append(
                f"""
### {qmd_escape(name)}

{''.join(rendered_answers)}
"""
            )

    missing_list = [
        data for data in responses
        if not response_received(data)
    ]
    missing_items = []
    for data in missing_list:
        recipient = data.get("recipient", {}) if isinstance(data.get("recipient"), dict) else {}
        missing_items.append(f"- {qmd_escape(recipient.get('name', ''))} — {qmd_escape(recipient.get('role', ''))}")

    inferred_received = [
        data for data in responses
        if response_has_entered_content(data) and not response_received_explicit(data)
    ]
    inferred_items = []
    for data in inferred_received:
        recipient = data.get("recipient", {}) if isinstance(data.get("recipient"), dict) else {}
        inferred_items.append(
            "- "
            + str(message(messages, "feedback.inferred_note")).format(
                name=qmd_escape(recipient.get("name", ""))
            )
        )

    validation_notes = (
        "\n".join(inferred_items)
        if inferred_items
        else message(messages, "feedback.no_validation_notes")
    )

    return render_localized_template(
        "feedback_summary.qmd",
        {
            "audit_title": qmd_escape(audit_title_value),
            "generated_date": date.today().isoformat(),
            "sent_count": sent_count,
            "received_count": received_count,
            "missing_count": missing_count,
            "overall_average": format_avg(overall_average),
            "recipient_rows": "\n".join(recipient_rows)
            or "| — | — | — | — | — | — | — | — |",
            "question_rows": "\n".join(question_rows) or "| — | — | — | — | — |",
            "detailed_rows": "\n".join(detailed_rows)
            or "| — | — | — | — | — | — |",
            "open_feedback": "".join(open_feedback_blocks)
            or message(messages, "feedback.no_open_feedback"),
            "missing_items": "\n".join(missing_items)
            or message(messages, "feedback.all_received"),
            "validation_notes": validation_notes,
        },
        language,
    )


def create_summary(project_root: Path) -> None:
    feedback_dir = project_root / "08_feedback"
    responses = load_response_files(feedback_dir)

    if not responses:
        raise SystemExit("No response templates found in 08_feedback/response/. Run --request first.")

    summary_path = feedback_dir / "feedback_summary.qmd"
    summary_path.write_text(
        build_summary_qmd(responses, language=read_project_language(project_root)),
        encoding="utf-8",
    )

    print(f"Feedback summary created: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create plain-text feedback requests and a single QMD feedback summary."
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--request",
        action="store_true",
        help="Create feedback request email bodies and response templates.",
    )
    mode.add_argument(
        "--summary",
        action="store_true",
        help="Create one feedback_summary.qmd from filled response templates.",
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Audit project root. Default: auto-detect from current directory.",
    )

    parser.add_argument(
        "--include-sponsor",
        action="store_true",
        help="Also generate a request for sponsor. By default only auditees are used.",
    )

    parser.add_argument(
        "--response-due-date",
        default="",
        help="Optional response due date to include in the request, e.g. 2026-04-15.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite generated request text files.",
    )

    parser.add_argument(
        "--reset-response-templates",
        action="store_true",
        help="Reset response YAML templates. This can delete entered feedback.",
    )

    args = parser.parse_args()
    script_path = Path(__file__).resolve()

    if args.project_root:
        project_root = args.project_root.resolve()
    else:
        project_root = find_project_root([Path.cwd(), script_path.parent, script_path.parent.parent])

    if args.request:
        create_requests(
            project_root=project_root,
            include_sponsor=args.include_sponsor,
            response_due_date=args.response_due_date,
            overwrite_requests=args.overwrite,
            reset_response_templates=args.reset_response_templates,
        )
    elif args.summary:
        create_summary(project_root)


if __name__ == "__main__":
    main()
