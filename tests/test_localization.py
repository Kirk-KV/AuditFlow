from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from string import Template

import pytest
import yaml
from typer.testing import CliRunner

from auditflow.ai.context import extract_workpaper_sections
from auditflow.cli import app
from auditflow.commands.audit_program import create_audit_program
from auditflow.commands.init_project import create_initial_project
from auditflow.commands.planning import create_planning_files
from auditflow.commands.workpapers import generate_workpapers
from auditflow.localization import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    load_messages,
    read_project_language,
)


LOCALIZED_TEMPLATES = {
    "audit_story.qmd",
    "evidence_readme.md",
    "feedback_readme.md",
    "feedback_request.txt",
    "feedback_summary.qmd",
    "messages.yml",
    "notification_letter.md",
    "planning_document.qmd",
    "report.qmd",
    "stakeholders.yml",
    "team.yml",
    "timeline.yml",
    "workpaper.qmd",
}


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def invoke(runner: CliRunner, *args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, f"{result.output}\n{result.exception!r}"
    return result.output


def template_placeholders(content: str) -> set[str]:
    result: set[str] = set()
    for match in Template.pattern.finditer(content):
        name = match.group("named") or match.group("braced")
        if name:
            result.add(name)
    return result


def message_shape(value: object) -> object:
    if isinstance(value, dict):
        return {key: message_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [message_shape(item) for item in value]
    return type(value).__name__


def test_locales_have_matching_templates_messages_and_placeholders() -> None:
    templates_root = Path(__file__).resolve().parents[1] / "auditflow" / "templates"
    locale_files = {
        language: {path.name for path in (templates_root / language).iterdir() if path.is_file()}
        for language in SUPPORTED_LANGUAGES
    }

    assert locale_files["en"] == LOCALIZED_TEMPLATES
    assert locale_files["ru"] == LOCALIZED_TEMPLATES
    assert message_shape(load_messages("en")) == message_shape(load_messages("ru"))

    for name in LOCALIZED_TEMPLATES - {"messages.yml"}:
        en_content = (templates_root / "en" / name).read_text(encoding="utf-8")
        ru_content = (templates_root / "ru" / name).read_text(encoding="utf-8")
        assert template_placeholders(en_content) == template_placeholders(ru_content), name


def test_project_without_settings_uses_english(tmp_path: Path) -> None:
    project = tmp_path / "legacy_project"
    (project / "00_admin").mkdir(parents=True)
    assert read_project_language(project) == DEFAULT_LANGUAGE


def test_init_rejects_unsupported_language(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["init", str(tmp_path / "audit"), "--language", "de"],
    )
    assert result.exit_code == 2
    assert "Supported values: en, ru" in result.output


def test_russian_cli_lifecycle_generates_russian_documents(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "russian_audit"
    project_arg = str(project)

    invoke(runner, "init", project_arg, "--language", "ru")
    assert read_project_language(project) == "ru"
    assert "Папка доказательств" in (project / "04_evidence" / "README.md").read_text(
        encoding="utf-8"
    )

    write_yaml(
        project / "initial_data.yml",
        {
            "audit": {
                "id": "2026-RU-001",
                "title": "Аудит закупок",
                "company": "Пример",
                "source": "annual_audit_plan",
            },
            "objectives": [{"id": "OBJ-001", "statement": "Проверить согласование закупок."}],
            "period": {"from": "2026-01-01", "to": "2026-03-31"},
            "scope": {
                "in_scope": ["Согласование закупок"],
                "out_of_scope": [],
                "rationale": ["Ключевой превентивный контроль"],
            },
            "risks": [
                {
                    "id": "R-001",
                    "title": "Закупка проведена без согласования",
                    "rationale": "Возможно несанкционированное обязательство.",
                }
            ],
        },
    )
    write_yaml(
        project / "00_admin" / "stakeholders.yml",
        {
            "sponsor": {"name": "Заказчик", "role": "Директор", "email": "s@example.test"},
            "auditees": [
                {
                    "name": "Владелец процесса",
                    "role": "Руководитель закупок",
                    "email": "o@example.test",
                }
            ],
            "additional_stakeholders": [],
            "report_recipients": [],
        },
    )

    invoke(runner, "create", "planning", "--project", project_arg)
    planning = (project / "01_planning" / "planning_document.qmd").read_text(
        encoding="utf-8"
    )
    assert "Планирование аудита" in planning
    assert "## 6. Риски" in planning

    write_yaml(
        project / "01_planning" / "planning_decision.yml",
        {
            "overall_conclusion": "Провести тестирование контроля.",
            "scope": {
                "in_scope": ["Согласование закупок"],
                "out_of_scope": [],
                "rationale": ["Риск существенен"],
            },
            "included_risks": [
                {
                    "id": "R-001",
                    "title": "Закупка проведена без согласования",
                    "rationale": "Контроль подлежит тестированию.",
                }
            ],
            "excluded_risks": [],
            "controls": [
                {
                    "id": "C-001",
                    "risk_id": "R-001",
                    "description": "Закупка согласуется до размещения.",
                    "owner": "Руководитель закупок",
                    "design_assessment": "Дизайн адекватен",
                    "planning_approach": "Проверить операционную эффективность.",
                }
            ],
            "recommended_tests": [],
        },
    )
    invoke(runner, "create", "audit-program", "--project", project_arg)
    program_path = project / "03_audit_program" / "audit_program.yml"
    program = yaml.safe_load(program_path.read_text(encoding="utf-8"))
    assert "рабочую матрицу" in program["program"]["note"]
    program["program"]["status"] = "approved"
    program["program_rows"][0]["test_hypothesis"] = "Возможны закупки без согласования."
    program["program_rows"][0]["test_script"] = ["Сопоставить закупки и согласования."]
    write_yaml(program_path, program)

    invoke(runner, "create", "workpapers", "--project", project_arg)
    workpaper_path = project / "05_workpapers" / "WP-C-001.qmd"
    workpaper = workpaper_path.read_text(encoding="utf-8")
    assert "## Выполненная работа" in workpaper
    assert "## Предлагаемое наблюдение" in workpaper
    workpaper = workpaper.replace(
        "Кратко изложите результаты теста.",
        "Выявлено одно подтвержденное исключение.",
    ).replace(
        "Сформулируйте вывод по рабочей бумаге.",
        "Контроль сработал не во всех случаях.",
    ).replace(
        '  title: ""',
        '  title: "Закупка без согласования"',
    )
    workpaper_path.write_text(workpaper, encoding="utf-8")

    sections = extract_workpaper_sections(workpaper)
    assert "Выявлено одно подтвержденное исключение." in sections["Results"]
    assert "Контроль сработал" in sections["Conclusion"]

    invoke(runner, "create", "observations", "--project", project_arg)
    observation_path = project / "06_observations" / "OBS-001.yml"
    assert observation_path.exists()
    observation = yaml.safe_load(observation_path.read_text(encoding="utf-8"))
    observation.update(
        {
            "status": "validated",
            "severity": "High",
            "condition": "Одна закупка проведена до согласования.",
            "criteria": "Закупки должны быть согласованы до размещения.",
            "cause": "Настройки системы позволяли обойти согласование.",
            "risk_effect": "Возможно принятие несанкционированных обязательств.",
            "recommendation": "Настроить блокирующий контроль.",
            "executive_summary": "Контроль согласования сработал не во всех случаях.",
        }
    )
    write_yaml(observation_path, observation)

    invoke(runner, "create", "report", "--project", project_arg)
    report = (project / "07_reporting" / "report.qmd").read_text(encoding="utf-8")
    assert "# Резюме для руководства" in report
    assert "Фактическое состояние" in report
    assert "Высокая" in report

    invoke(runner, "feedback", "request", "--project", project_arg)
    request = next((project / "08_feedback" / "request").glob("*_request.txt"))
    assert "Запрос обратной связи" in request.read_text(encoding="utf-8")
    invoke(runner, "feedback", "summary", "--project", project_arg)
    summary = (project / "08_feedback" / "feedback_summary.qmd").read_text(
        encoding="utf-8"
    )
    assert "# Итоги обратной связи" in summary

    invoke(runner, "create", "archive", "--project", project_arg)
    archive = (project / "09_archive" / "audit_story.qmd").read_text(encoding="utf-8")
    assert "# История аудита на одной странице" in archive
    assert "Закупка без согласования" in archive


@pytest.mark.integration
def test_russian_qmd_renders_when_quarto_is_available(tmp_path: Path) -> None:
    quarto = shutil.which("quarto")
    if quarto is None:
        pytest.skip("Quarto is not available on PATH")

    project = tmp_path / "russian_render"
    create_initial_project(project, language="ru")
    write_yaml(
        project / "initial_data.yml",
        {
            "audit": {"id": "RU-001", "title": "Тестовый аудит", "company": "Пример"},
            "objectives": [{"id": "OBJ-001", "statement": "Проверить контроль."}],
            "scope": {"in_scope": ["Процесс"], "out_of_scope": [], "rationale": []},
            "risks": [{"id": "R-001", "title": "Риск", "rationale": "Обоснование"}],
        },
    )
    create_planning_files(project)
    write_yaml(
        project / "01_planning" / "planning_decision.yml",
        {
            "included_risks": [{"id": "R-001", "title": "Риск", "rationale": "Важно"}],
            "excluded_risks": [],
            "controls": [
                {
                    "id": "C-001",
                    "risk_id": "R-001",
                    "description": "Контроль",
                    "owner": "Владелец",
                }
            ],
        },
    )
    create_audit_program(project)
    generate_workpapers(project)

    for document in (
        "01_planning/planning_document.qmd",
        "05_workpapers/WP-C-001.qmd",
    ):
        subprocess.run(
            [quarto, "render", document],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        assert (project / Path(document).with_suffix(".html")).exists()
