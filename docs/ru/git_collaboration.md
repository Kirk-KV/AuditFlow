# Совместная работа через Git

[English](../git_collaboration.md) | **Русский**

Git необязателен: AuditFlow работает как обычная локальная папка без GitHub, GitLab или Azure DevOps.

Если команде нужна версионность и review менеджера:

```powershell
git checkout -b audit/planning-update
git add initial_data.yml 01_planning 03_audit_program
git commit -m "Update audit planning"
git push -u origin audit/planning-update
```

После этого создайте pull/merge request. Менеджер может просматривать изменения, оставлять комментарии и требовать исправления до слияния.

Исходные данные, регламенты и переписку обычно не следует помещать в Git. Добавьте их в `.gitignore`, а изменение контролируйте через evidence manifest:

```powershell
auditflow evidence status
auditflow evidence refresh
```

SHA-256 показывает, что файл изменился после фиксации manifest. Он не подтверждает автора, источник, полноту или подлинность доказательства и не заменяет защищенное хранилище.

