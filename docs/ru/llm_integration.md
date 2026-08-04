# Использование LLM

[English](../llm_integration.md) | **Русский**

AI в AuditFlow является вспомогательным инструментом. Он не утверждает наблюдения и не заменяет профессиональное суждение аудитора.

## Основные сценарии

```powershell
auditflow ai status
auditflow ai draft-observation WP-C-001
auditflow ai review-observation OBS-001
auditflow ai review-audit-program
```

Перед вызовом модели AuditFlow формирует ограниченный контекст и выполняет preflight. В контекст не должны автоматически включаться необработанные доказательства и test scripts.

## Поддерживаемые провайдеры

- `ollama` — локальная или корпоративная установка Ollama; Qwen3 8B используется как демонстрационная модель;
- `openai_compatible` — OpenAI и совместимые корпоративные шлюзы;
- `anthropic` — Claude через Anthropic Messages API.

OpenAI-совместимый адаптер по умолчанию использует JSON Schema. Для шлюза, который поддерживает только JSON mode, в policy можно задать `options.response_format: json_object`. 
Для Claude нужна модель с поддержкой structured outputs. Полученный объект в любом случае повторно проверяется локальной схемой AuditFlow.

## Настройка внешнего провайдера

Endpoint, модель и имя переменной с API-ключом задаются только в корпоративной policy.
Например, для OpenAI:

```yaml
profiles:
  external_openai:
    provider: openai_compatible
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    default_model: company-approved-openai-model
    allowed_models: [company-approved-openai-model]
    data_boundary: external
    allowed_classifications: [public, internal]
    options:
      response_format: json_schema
      temperature: 0

rules:
  allow_external_providers: true
  require_confirmation_for_external: true
```

Для Claude меняются профиль и endpoint:

```yaml
profiles:
  external_claude:
    provider: anthropic
    base_url: https://api.anthropic.com/v1
    api_key_env: ANTHROPIC_API_KEY
    default_model: company-approved-claude-model
    allowed_models: [company-approved-claude-model]
    data_boundary: external
    allowed_classifications: [public, internal]
    options:
      max_tokens: 4096
      temperature: 0
```

Ключи хранятся вне проекта:

```powershell
$env:OPENAI_API_KEY = "<key>"
$env:ANTHROPIC_API_KEY = "<key>"
```

После выбора разрешенного профиля в `00_admin/ai.yml` выполните `auditflow ai status`, а затем команду с `--dry-run`.
Эти команды задают ключи только для текущей PowerShell-сессии. В корпоративной среде ключи должен предоставлять ответственный сотрудник; хранить их в проекте или policy нельзя.

## Безопасность

Настройки проекта находятся в `00_admin/ai.yml`, корпоративная политика задается отдельно.
Перед использованием внешнего провайдера определите:

- какие классификации данных разрешено передавать;
- какие провайдеры и модели одобрены;
- требуется ли подтверждение пользователя;
- какие чувствительные данные должны блокироваться или маскироваться;
- где хранятся API-ключи и журналы запросов.

Проверка чувствительных данных основана на шаблонах и не может гарантировать безопасность промпта. Аудитор обязан просмотреть контекст до внешней отправки.

`ai.output_language` управляет языком ответа модели независимо от языка system prompts. Значение `auto` использует язык проекта из `00_admin/settings.yml`; язык можно указать и явно. Английские system prompts остаются общими, чтобы правила и JSON-контракт не
расходились между локализациями.
