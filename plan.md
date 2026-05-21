# Лабораторная работа №5 — Интеграция Ansible с облачной платформой Yandex Cloud

## Контекст

Цель работы — развернуть базовую инфраструктуру в Yandex Cloud и продемонстрировать четыре сценария интеграции с Ansible:
1. Provisioning виртуальных машин из плейбука.
2. Динамический инвентарь — Ansible сам находит созданные ВМ в облаке.
3. Configuration management — установка/настройка ПО (nginx) на созданных ВМ.
4. Teardown — корректное удаление всех созданных ресурсов.

Платформа Yandex Cloud выбрана из-за бесплатного стартового гранта (~4000 ₽ на 60 дней), полной поддержки со стороны Ansible-коллекции `yandex.cloud` и удобства для русскоязычного контекста. Control node будет крутиться в отдельной ВМ в облаке (production-like подход).

Каталог работы: `d:\work\gera\lab5\`. Существующий `lab5\main.py` — пустой и к лабе отношения не имеет (можно удалить или оставить заглушкой).

---

## Архитектура решения

```
┌─────────────────────────────────────────────┐
│ Yandex Cloud (облако, фолдер lab5-folder)   │
│                                             │
│   ┌──────────────┐      ┌─────────────────┐ │
│   │ control-node │ ───► │ web-1, web-2    │ │
│   │ (Ansible)    │ SSH  │ (target hosts)  │ │
│   │ Ubuntu 22.04 │      │ Ubuntu 22.04    │ │
│   └──────────────┘      └─────────────────┘ │
│         ▲                                   │
│         │ yc CLI / API                      │
└─────────┼───────────────────────────────────┘
          │
   Локальная Windows-машина (только bootstrap:
   yc init, ssh, первая выгрузка плейбуков)
```

---

## Этап 0. Подготовка (локально, ~30 мин)

1. Зарегистрировать аккаунт в Yandex Cloud (https://console.cloud.yandex.ru), активировать стартовый грант.
2. Создать платёжный аккаунт (требуется привязка карты, но списаний не будет в рамках гранта).
3. Создать **облако** и **каталог** `lab5-folder`.
4. Установить `yc` CLI на Windows (PowerShell):
   ```powershell
   iex (New-Object System.Net.WebClient).DownloadString('https://storage.yandexcloud.net/yandexcloud-yc/install.ps1')
   ```
5. Инициализировать профиль: `yc init` (выбрать облако, каталог, зону `ru-central1-a`).
6. Сгенерировать SSH-ключи: `ssh-keygen -t ed25519 -f $HOME/.ssh/lab5_key`.
7. Создать **сервисный аккаунт** `ansible-sa` с ролью `editor` в каталоге:
   ```powershell
   yc iam service-account create --name ansible-sa
   yc resource-manager folder add-access-binding lab5-folder --role editor --subject serviceAccount:<SA_ID>
   yc iam key create --service-account-name ansible-sa --output $HOME/.yc/key.json
   ```

**Артефакты на выходе этапа:** `yc` CLI настроен, есть SSH-ключи, есть `key.json` сервисного аккаунта.

---

## Этап 1. Bootstrap: создание control-node ВМ (~15 мин)

Создаём первую ВМ вручную через `yc`, на ней будет жить Ansible.

```powershell
yc compute instance create `
  --name control-node `
  --zone ru-central1-a `
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 `
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2204-lts,size=20 `
  --memory 2 --cores 2 `
  --ssh-key $HOME/.ssh/lab5_key.pub
```

Подключиться: `ssh -i $HOME/.ssh/lab5_key yc-user@<публичный_IP>`.

На control-node установить:
```bash
sudo apt update && sudo apt install -y python3-pip git
pip3 install ansible yandexcloud
ansible-galaxy collection install yandex.cloud
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
yc init   # через тот же OAuth-токен или authorized key
```

Скопировать `key.json` сервисного аккаунта и приватный SSH-ключ на control-node (через `scp`).

---

## Этап 2. Структура проекта Ansible

На control-node создать каталог `~/lab5/` со следующей структурой:

```
lab5/
├── ansible.cfg                  # inventory, host_key_checking=False, remote_user
├── inventory/
│   └── yacloud.yml              # dynamic inventory плагин yandex.cloud.yc
├── group_vars/
│   └── all.yml                  # folder_id, zone, image_family, ssh_user
├── playbooks/
│   ├── provision.yml            # создаёт web-1, web-2 через yandex.cloud.compute_instance
│   ├── configure.yml            # роль webserver на группе web
│   └── teardown.yml             # удаляет ВМ (state=absent)
└── roles/
    └── webserver/
        ├── tasks/main.yml       # apt install nginx, copy index, service started
        ├── templates/index.html.j2
        └── handlers/main.yml    # restart nginx
```

### Ключевые файлы

**`ansible.cfg`:**
```ini
[defaults]
inventory = ./inventory
host_key_checking = False
remote_user = ubuntu
private_key_file = ~/.ssh/lab5_key
stdout_callback = yaml
```

**`group_vars/all.yml`:** `folder_id`, `zone: ru-central1-a`, `subnet_id`, `image_family: ubuntu-2204-lts`, `ssh_pub_key` — переменные для модулей.

**`playbooks/provision.yml`** — использует модуль `yandex.cloud.compute_instance` из коллекции `yandex.cloud` (https://github.com/yandex-cloud/yc-ansible). Для каждой ВМ:
- задать `name`, `zone_id`, `platform_id: standard-v3`
- ресурсы: `resources_spec` (cores=2, memory=2)
- boot disk из `image-family`
- `network_interfaces` с публичным IP
- `metadata`: `ssh-keys: ubuntu:<key>`
- зарегистрировать выходные данные через `register` и `add_host` для использования в той же сессии.

> Если коллекция `yandex.cloud` не покрывает нужный модуль (она частично поддерживается) — fallback на `ansible.builtin.command` с вызовом `yc compute instance create --format json` и парсингом JSON через `set_fact`.

**`playbooks/configure.yml`** — `hosts: web`, применяет роль `webserver`. Роль:
- `apt: name=nginx state=present update_cache=yes`
- `template: src=index.html.j2 dest=/var/www/html/index.html` (в шаблоне `{{ ansible_hostname }}` и `{{ ansible_default_ipv4.address }}`)
- `service: name=nginx state=started enabled=yes`
- handler: restart nginx.

**`playbooks/teardown.yml`** — `state: absent` для тех же ВМ, либо `yc compute instance delete --name web-1 -y` через `command`.

---

## Этап 3. Динамический инвентарь

В `inventory/yacloud.yml`:
```yaml
plugin: yandex.cloud.yc
service_account_key_file: ~/.yc/key.json
folder_id: <folder_id>
keyed_groups:
  - key: labels.role
    prefix: role
hostnames:
  - name
filters:
  - status == "RUNNING"
```

Проверка: `ansible-inventory -i inventory/yacloud.yml --graph` — должны увидеть группу `role_web` после провижининга, если у ВМ задана метка `role=web`.

> Если плагин не работает — заменить на скрипт `inventory/yc.py`, который вызывает `yc compute instance list --format json` и формирует JSON для Ansible. Минимальный скрипт ~30 строк на Python.

---

## Этап 4. End-to-end запуск (демонстрация)

Команды на control-node, в порядке выполнения:

```bash
# 1. Создать ВМ
ansible-playbook playbooks/provision.yml

# 2. Убедиться, что инвентарь подхватил новые ВМ
ansible-inventory --graph
ansible role_web -m ping

# 3. Накатить конфигурацию (nginx)
ansible-playbook playbooks/configure.yml

# 4. Проверить руками
curl http://<external_ip_web-1>
curl http://<external_ip_web-2>

# 5. Снести всё
ansible-playbook playbooks/teardown.yml
yc compute instance list  # должна остаться только control-node
```

---

## Этап 5. Отчёт по лабораторной

Подготовить документ (Word/PDF) с разделами:
1. Постановка задачи и выбор платформы (обоснование Yandex Cloud).
2. Архитектурная схема (см. выше).
3. Скриншоты:
   - `yc init` и созданный сервисный аккаунт;
   - вывод `ansible-playbook provision.yml`;
   - `ansible-inventory --graph` с найденными ВМ;
   - `curl http://<ip>` с ответом nginx;
   - вывод `teardown.yml` и пустой `yc compute instance list`.
4. Листинги ключевых файлов (`provision.yml`, `configure.yml`, `inventory/yacloud.yml`, роль `webserver`).
5. Выводы: что даёт интеграция (idempotency, IaC, repeatability), какие ограничения встретились.

---

## Критические файлы для создания

- `d:\work\gera\lab5\ansible.cfg`
- `d:\work\gera\lab5\inventory\yacloud.yml`
- `d:\work\gera\lab5\group_vars\all.yml`
- `d:\work\gera\lab5\playbooks\provision.yml`
- `d:\work\gera\lab5\playbooks\configure.yml`
- `d:\work\gera\lab5\playbooks\teardown.yml`
- `d:\work\gera\lab5\roles\webserver\tasks\main.yml`
- `d:\work\gera\lab5\roles\webserver\templates\index.html.j2`
- `d:\work\gera\lab5\README.md` (краткая инструкция запуска)

Файлы готовятся локально в Windows-репозитории (для сдачи), затем `scp` на control-node для выполнения. `lab5\main.py` удалить — он относился к другой лабе.

---

## Верификация (acceptance criteria)

- [ ] `yc compute instance list` показывает 3 ВМ после `provision.yml` (control-node + web-1 + web-2).
- [ ] `ansible role_web -m ping` возвращает `pong` для обеих web-ВМ.
- [ ] `curl http://<ip>:80` возвращает HTML с именем хоста из шаблона.
- [ ] Повторный запуск `configure.yml` показывает `changed=0` (идемпотентность).
- [ ] После `teardown.yml` в каталоге остаётся только control-node.
- [ ] Все ресурсы удалены до окончания гранта, чтобы не было списаний.

---

## Риски и подводные камни

- **Коллекция `yandex.cloud` для Ansible частично заброшена** — заранее проверить, что нужные модули работают на актуальной версии Python/Ansible; иметь fallback на `yc` CLI через `command`.
- **Квоты бесплатного гранта**: 2 vCPU и 2 ГБ ОЗУ суммарно достаточно, но новый аккаунт может иметь лимит по cores=4 в каталоге — может потребоваться запрос на увеличение.
- **SSH host key checking** — при первом подключении к свежесозданным ВМ нужно либо `host_key_checking = False`, либо явно собирать ключи через `ssh-keyscan` (в плейбуке после provisioning).
- **Race condition**: после `compute_instance create` ВМ ещё не готова к SSH — добавить `wait_for: port=22` перед запуском `configure.yml`.
- **Не забыть teardown** — иначе сгорит грант.

---

## Оценка трудозатрат

| Этап | Время |
|------|-------|
| 0. Регистрация и подготовка | 30 мин |
| 1. Bootstrap control-node | 15 мин |
| 2. Структура проекта и плейбуки | 2 ч |
| 3. Динамический инвентарь | 30 мин |
| 4. Отладка end-to-end | 1.5 ч |
| 5. Отчёт со скриншотами | 1 ч |
| **Итого** | **~6 ч** |
