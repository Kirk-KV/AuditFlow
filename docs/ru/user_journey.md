# Первый аудит в AuditFlow

[English](../user_journey.md) | **Русский**

## 1. Создание проекта

```powershell
auditflow init "C:/Audits/2026-001_procurement" --language ru
cd "C:/Audits/2026-001_procurement"
auditflow status
```

Язык записывается в `00_admin/settings.yml`. Не меняйте его после начала аудита без необходимости: уже созданные документы автоматически не переводятся.

## 2. Исходная информация

Заполните:

- `initial_data.yml` — тема, цели, период, предварительный периметр и риски;
- `00_admin/stakeholders.yml` — спонсор, владельцы процесса и получатели отчета;
- `00_admin/team.yml` — команда аудита;
- `00_admin/timeline.yml` — плановые даты;
- `00_admin/ai.yml` — настройки AI, если он используется.

YAML-ключи остаются английскими, значения можно полностью заполнять на русском.

## 3. Планирование

```powershell
auditflow create planning
quarto preview 01_planning/planning_document.qmd
```

Дополните `planning_document.qmd`, затем вручную зафиксируйте решение в `01_planning/planning_decision.yml`. Включайте в периметр только те риски, для которых понятно, почему они существенны и каким способом будут проверяться.

## 4. Программа аудита

```powershell
auditflow create audit-program
```

В `03_audit_program/audit_program.yml` заполните для каждой процедуры:

- `test_hypothesis` — что может быть не так;
- `test_script` — какие действия должен выполнить аудитор.

Повторный запуск сохраняет эти ручные поля. Перед филдом зафиксируйте статус программы в соответствии с правилами вашей команды.

## 5. Рабочие документы

```powershell
auditflow create workpapers
```

В каждом QMD опишите выполненную работу, добавьте Markdown-ссылки на фактически использованные файлы из `04_evidence`, зафиксируйте результаты и вывод.

```markdown
[Результат анализа](../04_evidence/99_generated/result.csv)
```

Если требуется наблюдение, заполните блок:

```yaml
proposed_observation:
  title: "Закупка проведена без обязательного согласования"
```

## 6. Наблюдения и отчет

```powershell
auditflow create observations
auditflow create report
quarto preview 07_reporting/report.qmd
```

Дополните файлы `06_observations/OBS-*.yml`: условие, критерий, причину, последствие, рекомендацию и план мероприятий. После этого проверьте автосформированные и ручные блоки отчета.

## 7. Обратная связь и архив

```powershell
auditflow feedback request
auditflow feedback summary
auditflow create archive
```

Исходные ответы сохраняйте в `08_feedback/response/original/`. Архивный QMD показывает, как исходные предпосылки превратились в итоговые выводы.

## 8. Финальная проверка

```powershell
auditflow timeline refresh
auditflow evidence status
auditflow validate --strict
```

Валидация проверяет структуру, ссылки и связи между артефактами. Содержательную оценку доказательств и выводов выполняют аудитор и проверяющий.

