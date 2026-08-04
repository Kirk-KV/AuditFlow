# Настройка AuditFlow

[English](../customization.md) | **Русский**

## Оформление

- `styles/auditflow.css` — общие стили документов;
- `styles/report.css` — оформление отчета;
- `styles/brand.css` — фирменные цвета и шрифты;
- `styles/quarto-html.yml` — общие настройки Quarto.

Корпоративный CSS можно передать при создании проекта:

```powershell
auditflow init . --language ru --brand-css "C:/company/brand.css" --report-css "C:/company/report.css"
```

## Языковые шаблоны

В пакете пользовательские документы находятся в `auditflow/templates/en/` и `auditflow/templates/ru/`. Общие YAML-контракты, схемы, CSS и AI system prompts не дублируются.

При добавлении нового локализуемого шаблона необходимо:

1. добавить одинаковый файл в `en/` и `ru/`;
2. сохранить одинаковые `$placeholder`;
3. добавить файл в package data;
4. обновить тест целостности локалей;
5. проверить lifecycle и Quarto для обоих языков.

Компания может расширять YAML дополнительными полями, если они не конфликтуют с обязательным контрактом. Более строгие правила следует закреплять в собственных схемах и процессе review.

