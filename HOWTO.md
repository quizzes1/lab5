# Пошаговая инструкция выполнения лабораторной №5

Этот документ — полный walkthrough от «голой винды» до сданной работы. Каждая команда, каждое поле, каждый ожидаемый результат.

Краткий план — в [plan.md](plan.md). Здесь — детали.

---

## Глоссарий (что есть что)

| Термин | Что это |
|--------|---------|
| **Yandex Cloud** | Облачная платформа Яндекса. Аналог AWS/Azure. |
| **Облако (Cloud)** | Верхний уровень иерархии. Создаётся один на аккаунт. |
| **Каталог (Folder)** | Контейнер внутри облака для группировки ресурсов. У нас будет один — `lab5-folder`. |
| **Зона доступности** | Физический дата-центр. У нас `ru-central1-a`. |
| **VM / Compute Instance** | Виртуальная машина. |
| **Сервисный аккаунт (SA)** | Робот-пользователь для API. Нам нужен, чтобы Ansible/yc мог создавать ВМ. |
| **`yc`** | CLI-утилита Yandex Cloud. Аналог `aws`/`az`. |
| **Ansible** | Инструмент управления конфигурацией. Запускается на control-node, ходит по SSH на target-ВМ. |
| **Control-node** | ВМ, на которой установлен Ansible и с которой запускаются плейбуки. |
| **Плейбук** | YAML-файл со списком действий для Ansible. |
| **Инвентарь** | Список хостов, с которыми работает Ansible. Может быть статическим (файл) или динамическим (генерируется на лету). |

---

## ЭТАП 0. Регистрация и подготовка окружения

### 0.1. Регистрация в Yandex Cloud

1. Открыть https://console.cloud.yandex.ru в браузере.
2. Нажать **«Войти»** (или **«Подключиться»**) → войти через Яндекс ID (логин/пароль от Яндекса).
   - Если аккаунта Яндекса нет — зарегистрировать на https://passport.yandex.ru.
3. После входа откроется консоль. Если это первый вход — будет предложено создать **облако** и **каталог**:
   - Имя облака: можно оставить дефолтное (`<твоё-имя>-cloud`).
   - Имя каталога: **`lab5-folder`** (важно — это имя используется в плейбуках).

### 0.2. Активация стартового гранта (бесплатные деньги)

1. В консоли слева внизу нажать на свой аккаунт → **«Биллинг»**.
2. Кнопка **«Создать платёжный аккаунт»**.
3. Заполнить:
   - Тип: **физическое лицо**.
   - ИНН — можно пропустить, если нет.
   - Привязать карту (любую Visa/MC/МИР). Спишут и тут же вернут 1 ₽ для проверки.
4. После привязки автоматически активируется **стартовый грант** ~4000 ₽ на 60 дней.
   - Проверить можно в разделе **«Биллинг» → «Платёжный аккаунт»**: должен появиться баланс «Грант».

> ⚠️ Без платёжного аккаунта ВМ создать нельзя, даже с грантом. Это требование Yandex Cloud.

### 0.3. Узнать свои ID (folder_id, cloud_id)

В консоли:
1. Слева сверху — выпадающий список с каталогами. Кликнуть → откроется список.
2. Навести курсор на `lab5-folder` → справа от имени появится иконка копирования ID.
3. **Записать folder_id** куда-нибудь в блокнот — он понадобится много раз.

Альтернатива — сделать позже через CLI: `yc config get folder-id`.

### 0.4. Установить `yc` CLI на Windows

Открыть **PowerShell** (Win+X → "Терминал" или "Windows PowerShell"):

```powershell
iex (New-Object System.Net.WebClient).DownloadString('https://storage.yandexcloud.net/yandexcloud-yc/install.ps1')
```

Скрипт установит `yc` в `%USERPROFILE%\yandex-cloud\bin\` и пропишет PATH.

**Закрой и заново открой PowerShell**, чтобы PATH обновился. Проверить:
```powershell
yc --version
```
Ожидаемый вывод: `Yandex Cloud CLI 0.xxx.x linux/amd64` (или похожее).

### 0.5. Инициализация `yc`

```powershell
yc init
```

Скрипт пошагово спросит:
1. **Welcome! ... Press Enter** → Enter.
2. Откроется браузер → войти под тем же Яндекс ID → подтвердить доступ → вернуться в терминал.
3. **Please choose cloud** → если у тебя одно облако, выбор сделается автоматически, иначе указать номер.
4. **Please choose folder** → выбрать номер строки с `lab5-folder`.
5. **Do you want to configure a default Compute zone?** → `Y`.
6. **Which zone do you want to use as a profile default?** → выбрать `ru-central1-a` (номер варьируется).

Проверить:
```powershell
yc config list
```
Должно показать: token, cloud-id, folder-id, compute-default-zone.

### 0.6. Сгенерировать SSH-ключи

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\lab5_key -N '""'
```

Объяснение:
- `-t ed25519` — современный алгоритм (быстрее и короче RSA).
- `-f $HOME\.ssh\lab5_key` — путь и имя ключа.
- `-N '""'` — пустой пароль (для лабы ок; в реальной жизни — обязательно пароль).

В результате появятся два файла:
- `C:\Users\<твой_логин>\.ssh\lab5_key` — приватный (никому не показывать).
- `C:\Users\<твой_логин>\.ssh\lab5_key.pub` — публичный (его положим на ВМ).

Если папки `.ssh` нет — `ssh-keygen` создаст её автоматически.

### 0.7. Создать сервисный аккаунт для Ansible

```powershell
# 1. Сам аккаунт
yc iam service-account create --name ansible-sa --description "SA for Ansible Lab 5"

# 2. Узнать его ID
yc iam service-account get --name ansible-sa
```

В выводе будет строка `id: ajeXXXXXXXX` — это **SA_ID**, сохрани.

```powershell
# 3. Узнать folder_id, если ещё не сохранил
yc config get folder-id

# 4. Выдать роль editor на каталог
yc resource-manager folder add-access-binding <ВСТАВЬ_FOLDER_ID> `
    --role editor `
    --subject serviceAccount:<ВСТАВЬ_SA_ID>

# 5. Создать ключ авторизации (JSON-файл)
mkdir $HOME\.yc -Force
yc iam key create --service-account-name ansible-sa --output $HOME\.yc\key.json
```

Должен появиться файл `C:\Users\<твой_логин>\.yc\key.json` со структурой:
```json
{
  "id": "...",
  "service_account_id": "ajeXXXX",
  "created_at": "...",
  "key_algorithm": "RSA_2048",
  "public_key": "...",
  "private_key": "..."
}
```

> 🔒 Этот файл = пароль от твоего облака. Не коммить в git, не шарь.

### 0.8. Узнать subnet_id

В каталоге `lab5-folder` уже есть default-сеть. Узнать ID её подсети в зоне `ru-central1-a`:
```powershell
yc vpc subnet list
```
Вывод выглядит так:
```
+----------------------+-----------------------+----------------------+----------------+---------------+------------------+
|          ID          |         NAME          |      NETWORK ID       |     ROUTE TABLE ID     |     ZONE      |      RANGE       |
+----------------------+-----------------------+----------------------+----------------+---------------+------------------+
| e9bxxxxxxxxxxxxxxx   | default-ru-central1-a | enpxxxxxxxxxx        |                |ru-central1-a  | [10.128.0.0/24]  |
+----------------------+-----------------------+----------------------+----------------+---------------+------------------+
```
Скопировать **ID** строки с зоной `ru-central1-a` — это **subnet_id**.

> Если default-сети нет (редкий случай) — `yc vpc network create --name default` и `yc vpc subnet create --name default-ru-central1-a --network-name default --zone ru-central1-a --range 10.128.0.0/24`.

### ✅ Контрольная точка этапа 0

У тебя должно быть:
- [ ] Аккаунт в Yandex Cloud, активирован грант.
- [ ] Записано: `folder_id`, `subnet_id`, `SA_ID`.
- [ ] `yc --version` работает.
- [ ] Файлы: `~/.ssh/lab5_key`, `~/.ssh/lab5_key.pub`, `~/.yc/key.json`.

---

## ЭТАП 1. Создание control-node ВМ

### 1.1. Создать ВМ через `yc`

```powershell
yc compute instance create `
  --name control-node `
  --hostname control-node `
  --zone ru-central1-a `
  --platform-id standard-v3 `
  --cores 2 --memory 2 `
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2204-lts,size=20 `
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 `
  --ssh-key $HOME\.ssh\lab5_key.pub `
  --labels role=control,lab=lab5
```

Команда вернёт JSON с описанием ВМ. Найти в нём:
- `network_interfaces[0].primary_v4_address.one_to_one_nat.address` — это **публичный IP** control-node.

Запиши его. Или потом:
```powershell
yc compute instance get control-node --format json | Select-String "address"
```

### 1.2. Подключиться к control-node по SSH

```powershell
ssh -i $HOME\.ssh\lab5_key yc-user@<ПУБЛИЧНЫЙ_IP_CONTROL_NODE>
```

При первом подключении спросит `Are you sure you want to continue connecting? (yes/no)` → ввести `yes`.

После входа промпт изменится на:
```
yc-user@control-node:~$
```

> 💡 На стандартных образах Ubuntu от Yandex Cloud имя пользователя — **`yc-user`**, не `ubuntu`. Но мы внутри ВМ работаем под `yc-user`, а на target-ВМ (web-1/web-2) — под `ubuntu`, потому что мы их так настроим в плейбуке.

### 1.3. Установить Ansible и зависимости на control-node

Выполнять команды **внутри SSH-сессии** (на control-node):

```bash
# Обновить пакеты
sudo apt update && sudo apt upgrade -y

# Поставить Python, pip, git
sudo apt install -y python3 python3-pip git

# Поставить Ansible и Python SDK Yandex Cloud
pip3 install --user ansible yandexcloud

# Добавить ~/.local/bin в PATH, если не добавлен
echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Проверка
ansible --version
```

Должен показать `ansible [core 2.x.x]`.

```bash
# Коллекция yandex.cloud НЕ нужна — она недоступна на Galaxy и репозиторий
# удалён с GitHub. Вместо неё используем yc CLI через ansible.builtin.command
# (так уже написаны плейбуки) и Python-скрипт inventory/yc_fallback.py
# для динамического инвентаря.

# Установить yc CLI и на control-node тоже
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
source ~/.bashrc
yc --version
```

### 1.4. Скопировать ключи на control-node

Открой **новый** PowerShell на Windows (старый — занят SSH-сессией):

```powershell
# SSH-ключ (его Ansible будет использовать для подключения к web-1/web-2)
scp -i $HOME\.ssh\lab5_key $HOME\.ssh\lab5_key yc-user@<IP_CONTROL_NODE>:~/.ssh/
scp -i $HOME\.ssh\lab5_key $HOME\.ssh\lab5_key.pub yc-user@<IP_CONTROL_NODE>:~/.ssh/

# Ключ сервисного аккаунта (yc будет им авторизовываться)
scp -i $HOME\.ssh\lab5_key $HOME\.yc\key.json yc-user@<IP_CONTROL_NODE>:~/key.json
```

Вернись в SSH-сессию на control-node:
```bash
mkdir -p ~/.yc
mv ~/key.json ~/.yc/key.json
chmod 600 ~/.ssh/lab5_key ~/.yc/key.json
```

### 1.5. Настроить `yc` на control-node под сервисный аккаунт

На control-node:
```bash
yc config profile create sa-profile
yc config set service-account-key ~/.yc/key.json
yc config set cloud-id <ВСТАВЬ_CLOUD_ID>     # узнать: на винде `yc config get cloud-id`
yc config set folder-id <ВСТАВЬ_FOLDER_ID>
yc config set compute-default-zone ru-central1-a

# Проверить, что работает
yc compute instance list
```

Должен показать одну ВМ — `control-node`.

### 1.6. Скопировать проект lab5 на control-node

С винды:
```powershell
scp -i $HOME\.ssh\lab5_key -r d:\work\gera\lab5 yc-user@<IP_CONTROL_NODE>:~/
```

На control-node проверить:
```bash
ls ~/lab5/
# Должен показать: ansible.cfg group_vars inventory playbooks plan.md README.md roles HOWTO.md
```

### ✅ Контрольная точка этапа 1

- [ ] `yc compute instance list` (с винды и с control-node) показывает 1 ВМ.
- [ ] Можешь зайти по SSH на control-node.
- [ ] На control-node: `ansible --version`, `yc --version`, `ls ~/lab5`, `ls ~/.yc/key.json`, `ls ~/.ssh/lab5_key`.

---

## ЭТАП 2. Подстановка реальных ID + выбор инвентаря

### ⚠️ Важно: какой инвентарь использовать

Все команды дальше **используют `inventory/yc_fallback.py`** (Python-скрипт, который вызывает `yc compute instance list`). Файл `inventory/yacloud.yml` оставлен как пример плагинного инвентаря, но требует несуществующую коллекцию — игнорируй его.

Сделай fallback исполняемым:
```bash
chmod +x ~/lab5/inventory/yc_fallback.py
```

Проверь, что скрипт работает:
```bash
~/lab5/inventory/yc_fallback.py
```
Должен вывести JSON со списком ВМ (пока только control-node).

### 2.1. Подставить реальные ID в group_vars/all.yml

На control-node:

```bash
cd ~/lab5
nano group_vars/all.yml
```

Заменить:
- `REPLACE_WITH_FOLDER_ID` → твой `folder_id`.
- `REPLACE_WITH_SUBNET_ID` → твой `subnet_id`.

Сохранить: `Ctrl+O`, `Enter`, `Ctrl+X`.

То же для `inventory/yacloud.yml`:
```bash
nano inventory/yacloud.yml
```
Заменить `REPLACE_WITH_FOLDER_ID`.

> 💡 Можно одной командой через `sed`:
> ```bash
> sed -i 's/REPLACE_WITH_FOLDER_ID/b1gxxxxxxx/' group_vars/all.yml inventory/yacloud.yml
> sed -i 's/REPLACE_WITH_SUBNET_ID/e9bxxxxxxx/' group_vars/all.yml
> ```

---

## ЭТАП 3. Запуск пайплайна

Все команды — на control-node, из директории `~/lab5`.

### 3.1. Provisioning — создание web-1 и web-2

```bash
ansible-playbook playbooks/provision.yml
```

Что произойдёт:
1. Ansible вызовет `yc compute instance list` → получит список существующих ВМ.
2. Для каждой ВМ из `web_hosts` (web-1, web-2), которой ещё нет, вызовет `yc compute instance create`.
3. Дождётся, пока на новых ВМ заработает порт 22 (SSH).
4. Покажет публичные IP.

Ожидаемый вывод заканчивается чем-то вроде:
```
ok: [localhost] => (item={'name': 'web-1', ...}) =>
  msg: VM web-1 → 158.160.X.X
ok: [localhost] => (item={'name': 'web-2', ...}) =>
  msg: VM web-2 → 158.160.Y.Y

PLAY RECAP *********************
localhost : ok=7 changed=2 unreachable=0 failed=0
```

Если что-то пошло не так — см. раздел «Траблшутинг» ниже.

### 3.2. Проверка динамического инвентаря

```bash
ansible-inventory --graph
```

Ожидаемый вывод:
```
@all:
  |--@ungrouped:
  |--@role_web:
  |  |--web-1
  |  |--web-2
  |--@role_control:
  |  |--control-node
  |--@lab_lab5:
  |  |--web-1
  |  |--web-2
  |  |--control-node
```

Если групп `role_web` нет — значит метки не подхватились или плагин не работает. Тогда:
```bash
ansible-inventory -i inventory/yc_fallback.py --graph
```

Проверить связь:
```bash
ansible role_web -m ping
```
Ожидаемый вывод (для каждой ВМ):
```
web-1 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### 3.3. Configuration management — настройка nginx

```bash
ansible-playbook playbooks/configure.yml
```

Ansible:
1. Подключится по SSH к web-1 и web-2.
2. Установит nginx через `apt`.
3. Положит шаблон страницы в `/var/www/html/index.nginx-debian.html`.
4. Запустит и включит сервис `nginx`.

Ожидаемый PLAY RECAP:
```
web-1 : ok=5  changed=3  unreachable=0  failed=0
web-2 : ok=5  changed=3  unreachable=0  failed=0
```

### 3.4. Проверка работы nginx

С control-node:
```bash
curl http://$(yc compute instance get web-1 --format json | python3 -c "import json,sys;print(json.load(sys.stdin)['network_interfaces'][0]['primary_v4_address']['one_to_one_nat']['address'])")
```

Или открыть в браузере: `http://<публичный_IP_web-1>`.

Должна показаться HTML-страница с таблицей: hostname, IP, ОС, ядро, CPU, RAM.

### 3.5. Проверка идемпотентности

Запусти `configure.yml` ещё раз:
```bash
ansible-playbook playbooks/configure.yml
```

Ожидаемый PLAY RECAP:
```
web-1 : ok=5  changed=0  unreachable=0  failed=0
web-2 : ok=5  changed=0  unreachable=0  failed=0
```

Все `changed=0` — это и есть идемпотентность.

### 3.6. Teardown — удаление web-ВМ

```bash
ansible-playbook playbooks/teardown.yml
```

Удалит ВМ с меткой `lab=lab5 AND role=web` (control-node останется, у неё `role=control`).

Проверить:
```bash
yc compute instance list
```
Должна остаться только `control-node`.

### ✅ Контрольная точка этапа 3

- [ ] `provision.yml` отработал, в облаке 3 ВМ.
- [ ] `ansible-inventory --graph` показывает группу `role_web` с двумя хостами.
- [ ] `ansible role_web -m ping` → pong.
- [ ] `curl http://<ip>` отвечает HTML.
- [ ] Повторный `configure.yml` → `changed=0`.
- [ ] `teardown.yml` удалил web-ВМ.

---

## ЭТАП 4. Сделать скриншоты для отчёта

Делаем скриншоты по мере прохождения пайплайна:

1. Консоль Yandex Cloud, где видны 3 ВМ.
2. Терминал с выводом `yc init`.
3. Терминал с выводом `ansible-playbook provision.yml` (вся PLAY RECAP).
4. Терминал с `ansible-inventory --graph`.
5. Терминал с `ansible role_web -m ping`.
6. Терминал с `ansible-playbook configure.yml`.
7. Браузер с открытой страницей http://web-1.
8. Терминал с `curl http://web-2`.
9. Терминал с повторным `configure.yml` (видно `changed=0`).
10. Терминал с `ansible-playbook teardown.yml`.
11. Терминал с `yc compute instance list` после teardown.

---

## ЭТАП 5. Финальная уборка

После сдачи работы удали control-node, чтобы не сжечь грант:

С винды:
```powershell
yc compute instance delete --name control-node
yc compute instance list  # пусто
```

Можно ещё удалить сервисный аккаунт:
```powershell
yc iam service-account delete --name ansible-sa
```

---

## Траблшутинг

### «Permission denied (publickey)» при SSH
- Проверь права на ключ: `chmod 600 ~/.ssh/lab5_key`.
- Проверь, что подключаешься под `yc-user`, а не `root` или `ubuntu`.
- Проверь, что при создании ВМ передал правильный `.pub` ключ.

### «Error: no folder-id specified»
- `yc config get folder-id` — пусто? → `yc config set folder-id <ID>`.

### Коллекция `yandex.cloud` не ставится
- Это ожидаемо: коллекция удалена с Galaxy, репозиторий `yandex-cloud/yc-ansible` на GitHub тоже больше не существует.
- В проекте уже подключён [yc_fallback.py](inventory/yc_fallback.py) (см. `ansible.cfg`), он работает через `yc` CLI и заменяет коллекцию полностью. Ничего ставить не нужно.

### `yc_fallback.py: Permission denied`
- Не выставлен +x: `chmod +x ~/lab5/inventory/yc_fallback.py`.

### `yc_fallback.py: bad interpreter` или `env: 'python3'`
- На control-node нет python3: `sudo apt install -y python3`.

### `ansible-inventory --graph` показывает только `@all` без хостов
- Скрипт работает, но `yc` не настроен. Проверь: `yc compute instance list` должен вернуть список. Если ошибка авторизации — см. этап 1.5 (настройка `yc config` на control-node под SA).

### Плагин `yandex.cloud.yc` в инвентаре не работает
- Использовать fallback: `ansible-inventory -i inventory/yc_fallback.py --graph`.
- В плейбуках для запуска через fallback: `ansible-playbook -i inventory/yc_fallback.py playbooks/configure.yml`.

### `provision.yml` падает с «quota exceeded»
- У нового аккаунта лимит cores=4. У нас 3 ВМ × 2 vCPU = 6 → перебор.
- Решение: уменьшить `vm_defaults.cores` в `group_vars/all.yml` до 1, либо запросить увеличение квоты в консоли (Поддержка → Создать запрос).

### `wait_for: port=22` падает с timeout
- ВМ ещё не загрузилась. Подожди минуту и запусти `configure.yml` снова — он подключится к уже готовой ВМ.

### Грант кончается
- Зайти в **Биллинг** и проверить остаток. Если близко к нулю — срочно `teardown.yml` + удалить control-node.

---

## Что сдать преподавателю

1. **Папку `lab5/`** — все плейбуки, конфиги, роли.
2. **Отчёт (Word/PDF)** с:
   - постановкой задачи,
   - архитектурной схемой (из [plan.md](plan.md)),
   - скриншотами всех этапов,
   - листингами ключевых файлов,
   - выводами.
