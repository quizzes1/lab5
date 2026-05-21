# Лабораторная работа №5

Интеграция Ansible с облачной платформой Yandex Cloud:
provisioning ВМ, динамический инвентарь, configuration management, teardown.

Подробный план: [plan.md](plan.md).

## Структура

```
lab5/
├── plan.md                       подробный план работы
├── README.md                     этот файл
├── ansible.cfg
├── group_vars/
│   └── all.yml                   folder_id, zone, subnet_id, ssh_pub_key
├── inventory/
│   ├── yc_fallback.py            ⭐ основной динамический инвентарь (через `yc` CLI)
│   └── yacloud.yml               пример плагинного инвентаря (не используется — коллекция yandex.cloud недоступна)
├── playbooks/
│   ├── provision.yml             создаёт web-1, web-2
│   ├── configure.yml             ставит nginx через роль webserver
│   └── teardown.yml              удаляет web-ВМ
└── roles/
    └── webserver/
        ├── tasks/main.yml
        ├── handlers/main.yml
        └── templates/index.html.j2
```

## Что нужно подставить перед запуском

В [group_vars/all.yml](group_vars/all.yml) и [inventory/yacloud.yml](inventory/yacloud.yml):

| Плейсхолдер | Откуда взять |
|-------------|--------------|
| `REPLACE_WITH_FOLDER_ID` | `yc config get folder-id` |
| `REPLACE_WITH_SUBNET_ID` | `yc vpc subnet list` |

SSH-ключ ожидается в `~/.ssh/lab5_key(.pub)`. Ключ сервисного аккаунта — в `~/.yc/key.json`.

## Быстрый старт (на control-node ВМ)

```bash
# 1. Подготовка окружения
sudo apt update && sudo apt install -y python3-pip
pip3 install ansible yandexcloud
# Коллекция yandex.cloud НЕ нужна — она удалена с Galaxy и GitHub.
# Проект работает через yc CLI + Python-скрипт inventory/yc_fallback.py.
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
yc init

# 2. Скопировать проект
scp -r lab5/ yc-user@<control-node-ip>:~/

# 3. Запуск
cd ~/lab5
ansible-playbook playbooks/provision.yml      # создать web-1, web-2
ansible-inventory --graph                     # увидеть группу role_web
ansible role_web -m ping                      # pong
ansible-playbook playbooks/configure.yml      # установить nginx
curl http://<external_ip_web-1>               # увидеть HTML
ansible-playbook playbooks/teardown.yml       # удалить web-ВМ
```

## Инвентарь

По умолчанию (через `ansible.cfg`) используется `inventory/yc_fallback.py` — Python-скрипт, который вызывает `yc compute instance list --format json` и формирует инвентарь. Группировка идёт по меткам (label) ВМ: `role=web` → группа `role_web`, `lab=lab5` → группа `lab_lab5`.

Перед первым запуском:
```bash
chmod +x inventory/yc_fallback.py
ansible-inventory --graph    # проверить, что инвентарь подхватывается
```

## Критерии приёмки

- [ ] `yc compute instance list` → 3 ВМ после `provision.yml`.
- [ ] `ansible role_web -m ping` → `pong` × 2.
- [ ] `curl http://<ip>:80` → HTML с именем хоста из шаблона.
- [ ] Повторный запуск `configure.yml` → `changed=0` (идемпотентность).
- [ ] После `teardown.yml` остаётся только `control-node`.
