# Отчёт по лабораторной №5

LaTeX-исходник для отчёта в стиле образца [Lab_5.pdf](../Lab_5.pdf).

## Чем собирать

### Вариант 1: Overleaf (онлайн, ничего не ставить)

1. https://www.overleaf.com → **New Project → Upload Project** → загрузить `report.tex`.
2. В меню **Menu** слева вверху выставить:
   - **Compiler:** `pdfLaTeX`
   - **TeX Live version:** последняя
3. Нажать **Recompile**. На выходе — PDF.

### Вариант 2: Локально через TeX Live (Windows)

```powershell
# Установка (один раз, ~3 ГБ)
winget install --id TeXLive.TeXLive

# Сборка
cd d:\work\gera\lab5\report
pdflatex report.tex
pdflatex report.tex   # второй прогон нужен для оглавления
```

В результате появится `report.pdf`.

### Вариант 3: Docker (если не хочется ставить TeX Live)

```powershell
docker run --rm -v ${PWD}:/work -w /work texlive/texlive:latest pdflatex report.tex
docker run --rm -v ${PWD}:/work -w /work texlive/texlive:latest pdflatex report.tex
```

## Что нужно отредактировать перед сдачей

В [report.tex](report.tex) проверить и поменять при необходимости:

| Что | Где (примерно) | Значение |
|-----|----------------|----------|
| ФИО, группа, преподаватель | титульный лист | `Артеев Д. Д.`, `5130904/50501`, `Степина Н. О.` |
| Год | титульный лист | `2026` |
| IP-адреса ВМ | секции 2.1.4, 2.4, 2.5 | свои реальные после `provision.yml` |
| ID ВМ (`fhm...`), сервисного аккаунта | везде | свои реальные |
| Скриншоты (если нужны) | вставить через `\includegraphics{...}` | свои файлы |

## Добавление скриншотов

Положить картинки в `report/img/`. Вставка:

```latex
\begin{figure}[h]
    \centering
    \includegraphics[width=0.9\textwidth]{img/yc_init.png}
    \caption{Вывод yc init}
\end{figure}
```

Дополнительно в преамбуле уже подключён `graphicx`.
