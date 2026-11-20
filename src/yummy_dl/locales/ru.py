"""Russian translations, keyed by the English source text.

Plural entries are (1, 2-4, 5+) forms: «1 файл», «2 файла», «5 файлов».
tests/test_i18n.py checks that every source string is here and that {placeholders} match.
"""

MESSAGES: dict[str, str | tuple[str, str, str]] = {
    # --- main window ---------------------------------------------------------------
    "&Settings": "&Настройки",
    "API &token…": "&Токен API…",
    "&Dark theme": "&Тёмная тема",
    "&Language": "&Язык",
    "System default ({lang})": "Как в системе ({lang})",
    "Open &config folder": "Открыть папку &настроек",
    "S&cripts": "С&крипты",
    "&Help": "&Справка",
    "&Quick start": "&Быстрый старт",
    "Set up API &token…": "Настроить &токен API…",
    "&Command-line usage": "&Командная строка",
    "&About yummy-dl": "&О программе",
    "Search anime, e.g. берсерк or Re:Zero": "Поиск аниме, например: берсерк или Re:Zero",
    "Search": "Найти",
    "Search for a title to begin.": "Найдите аниме, чтобы начать.",
    "Click to view full screen": "Нажмите, чтобы открыть на весь экран",
    "Browse…": "Обзор…",
    "Dub:": "Озвучка:",
    "Player:": "Плеер:",
    "Max quality:": "Макс. качество:",
    "Save to:": "Сохранять в:",
    "All": "Все",
    "None": "Ни одной",
    "Download selected": "Скачать выбранные",
    "Episodes:": "Серии:",
    "Title": "Название",
    "Episode": "Серия",
    "Dub": "Озвучка",
    "Progress": "Прогресс",
    "Status": "Статус",
    "Cancel selected": "Отменить выбранные",
    "Clear finished": "Убрать завершённые",
    "Open folder": "Открыть папку",
    "Queue (double-click to open, right-click to run a script):":
        "Очередь (двойной щелчок — открыть, правый щелчок — запустить скрипт):",
    "ffmpeg not found: Kodik saves as .ts, Aksor won't work":
        "ffmpeg не найден: Kodik сохраняется в .ts, Aksor не будет работать",
    "Searching “{query}”…": "Поиск «{query}»…",
    "{n} result": ("{n} результат", "{n} результата", "{n} результатов"),
    "Nothing found": "Ничего не найдено",
    "Loading…": "Загрузка…",
    "{n} ep.": "{n} эп.",
    "No downloadable dubs (supported: CVH, Kodik, Aksor).":
        "Нет озвучек, которые можно скачать (поддерживаются: CVH, Kodik, Aksor).",
    "Auto": "Авто",
    "Episode {ep}": "Серия {ep}",
    "✓ downloaded": "✓ скачано",
    "{n} of {total} selected": "Выбрано {n} из {total}",
    "Download folder": "Папка для загрузок",
    "Token saved": "Токен сохранён",
    "Token removed": "Токен удалён",
    "Queued {n} episode": ("В очередь добавлена {n} серия", "В очередь добавлены {n} серии",
                           "В очередь добавлено {n} серий"),
    "Restart yummy-dl now to switch the language?": "Перезапустить yummy-dl сейчас, чтобы сменить язык?",
    "{n} job is still running and will be stopped (downloads resume when re-added).": (
        "{n} задача ещё выполняется и будет остановлена (загрузку можно продолжить, добавив её снова).",
        "{n} задачи ещё выполняются и будут остановлены (загрузки можно продолжить, добавив их снова).",
        "{n} задач ещё выполняются и будут остановлены (загрузки можно продолжить, добавив их снова).",
    ),
    "The new language will be used the next time you start the app.":
        "Новый язык будет использоваться при следующем запуске программы.",
    "Couldn't restart automatically. Please start yummy-dl again.":
        "Не удалось перезапустить автоматически. Запустите yummy-dl ещё раз.",
    "{n} job still running. Quit anyway?": (
        "{n} задача ещё выполняется. Всё равно выйти?",
        "{n} задачи ещё выполняются. Всё равно выйти?",
        "{n} задач ещё выполняются. Всё равно выйти?",
    ),
    "(Partial downloads resume next time; unfinished scripts keep the original file.)":
        "(Недокачанные серии продолжатся в следующий раз; при незавершённом скрипте исходный файл сохраняется.)",
    "Poster": "Постер",
    "Loading full resolution…": "Загрузка полного размера…",
    "click or press Esc to close": "щёлкните или нажмите Esc, чтобы закрыть",

    # --- queue statuses ---------------------------------------------------------------
    "Queued": "В очереди",
    "Downloading": "Загрузка",
    "Done": "Готово",
    "Exists": "Уже есть",
    "Failed": "Ошибка",
    "Cancelled": "Отменено",
    "Running script": "Выполняется скрипт",
    "partial download kept, re-add to resume": "недокачанное сохранено, добавьте снова, чтобы продолжить",
    "original kept": "исходный файл сохранён",
    "(original kept)": "(исходный файл сохранён)",
    "(+{n} more)": "(и ещё {n})",

    # --- scripts (menu, runs) ---------------------------------------------------------
    "&Manage scripts…": "&Управление скриптами…",
    "No scripts yet: add one in Manage scripts…": "Скриптов пока нет: добавьте в «Управление скриптами…»",
    "(auto)": "(авто)",
    "Run on &files…": "Запустить для &файлов…",
    "Run on a f&older…": "Запустить для п&апки…",
    "It will be overwritten when you save.": "Он будет перезаписан при сохранении.",
    "Scripts saved": "Скрипты сохранены",
    "Run '{name}' on…": "Запустить «{name}» для…",
    "Videos ({exts});;All files (*)": "Видео ({exts});;Все файлы (*)",
    "Run '{name}' on every video in…": "Запустить «{name}» для всех видео в папке…",
    "Scripts need ffmpeg, and it wasn't found.\n"
    "Windows: run  winget install ffmpeg  or put ffmpeg.exe next to yummy-dl-gui.exe.":
        "Для скриптов нужен ffmpeg, но он не найден.\n"
        "Windows: выполните  winget install ffmpeg  или положите ffmpeg.exe рядом с yummy-dl-gui.exe.",
    "No video files found there (or they're already queued).": "Видеофайлы не найдены (или они уже в очереди).",
    "Run script": "Запустить скрипт",
    "Run '{name}' on {n} file?": ("Запустить «{name}» для {n} файла?", "Запустить «{name}» для {n} файлов?",
                                  "Запустить «{name}» для {n} файлов?"),
    "Each original is deleted after its conversion succeeds. If ffmpeg fails, the original is kept.":
        "Исходный файл удаляется после успешной обработки. Если ffmpeg завершится с ошибкой, он сохранится.",
    "Don't ask again until I restart the app": "Не спрашивать до перезапуска программы",
    "Queued '{name}' on {n} file": ("«{name}»: в очереди {n} файл", "«{name}»: в очереди {n} файла",
                                    "«{name}»: в очереди {n} файлов"),

    # --- scripts dialog ---------------------------------------------------------------
    "Scripts": "Скрипты",
    "New": "Новый",
    "New script": "Новый скрипт",
    "From example ▾": "Из примера ▾",
    "Duplicate": "Копировать",
    "Delete": "Удалить",
    "Optional: what it's for": "Необязательно: для чего он",
    "Save the results in a folder named after the video (useful when cutting into parts)":
        "Сохранять результат в папку с именем видео (удобно при нарезке на части)",
    "Run automatically after each download (only one script can)":
        "Запускать автоматически после каждой загрузки (только один скрипт)",
    "ffmpeg was not found, so scripts can't run yet. On Windows: winget install ffmpeg.":
        "ffmpeg не найден, поэтому скрипты пока не запустятся. В Windows: winget install ffmpeg.",
    "Name:": "Название:",
    "Comment:": "Комментарий:",
    "ffmpeg command:": "Команда ffmpeg:",
    "Delete '{name}'?": "Удалить «{name}»?",
    "(no name)": "(без названия)",
    "Another script is also named '{name}'.": "Есть другой скрипт с названием «{name}».",
    "Couldn't save: {error}": "Не удалось сохранить: {error}",
    "Discard your unsaved changes?": "Отменить несохранённые изменения?",
    "Write the ffmpeg arguments; <code>ffmpeg</code> itself is optional. Placeholders:<br>"
    "<code>{input}</code> the episode file &nbsp; <code>{name}</code> its name without extension &nbsp; "
    "<code>{ext}</code> its extension &nbsp; <code>{episode}</code> episode number (01) &nbsp; "
    "<code>{outdir}</code> where to write the result<br>"
    "Placeholders need no quotes, but quote a path where <i>you</i> type a space: "
    "<code>\"{outdir}/{episode} {name}.mkv\"</code><br>"
    "Keep <code>{name}</code> in output names (optionally after <code>{episode}</code>) so the app still "
    "sees the episode as downloaded.<br>"
    "<b>After a successful run the original file is deleted</b>; if ffmpeg fails it is kept.":
        "Напишите аргументы ffmpeg; само слово <code>ffmpeg</code> можно не писать. Подстановки:<br>"
        "<code>{input}</code> файл серии &nbsp; <code>{name}</code> его имя без расширения &nbsp; "
        "<code>{ext}</code> расширение &nbsp; <code>{episode}</code> номер серии (01) &nbsp; "
        "<code>{outdir}</code> куда записать результат<br>"
        "Подстановки не нужно брать в кавычки, но путь, в котором <i>вы</i> ставите пробел, нужно: "
        "<code>\"{outdir}/{episode} {name}.mkv\"</code><br>"
        "Оставляйте <code>{name}</code> в имени результата (можно после <code>{episode}</code>), "
        "чтобы программа видела серию как скачанную.<br>"
        "<b>После успешного выполнения исходный файл удаляется</b>; при ошибке ffmpeg он сохраняется.",

    # --- scripts core -----------------------------------------------------------------
    "x264/MP3 MKV 720p": "x264/MP3 MKV 720p",
    "x264/MP3 MKV 720p, 10-min parts": "x264/MP3 MKV 720p, части по 10 мин",
    "Remux to MKV (no re-encode)": "Перепаковка в MKV (без перекодирования)",
    "Re-encode to H.264 + MP3 192k, scaled to 720p. Plays on simple hardware players.":
        "Перекодирование в H.264 + MP3 192k с уменьшением до 720p. Играет на простых плеерах.",
    "Same conversion, cut into 10-minute pieces inside a folder named after the video.":
        "То же перекодирование с нарезкой на части по 10 минут в папку с именем видео.",
    "Change the container to MKV without touching video or audio. Takes seconds.":
        "Смена контейнера на MKV без изменения видео и звука. Занимает секунды.",
    "can't read {path}: {error}": "не удалось прочитать {path}: {error}",
    "'{name}' matches several scripts: {names}": "«{name}» подходит к нескольким скриптам: {names}",
    "none saved": "нет сохранённых",
    "no script named '{name}' (have: {names})": "нет скрипта «{name}» (есть: {names})",
    "can't parse the command: {error}": "не удалось разобрать команду: {error}",
    "Give the script a name.": "Дайте скрипту название.",
    "The command must read {input}, e.g. -i {input}.": "Команда должна читать {input}, например: -i {input}.",
    "The command must write into {outdir}, e.g. {outdir}/{name}.mkv.":
        "Команда должна писать в {outdir}, например: {outdir}/{name}.mkv.",
    'The output path has a space in it, so it was split in two. Wrap it in quotes: "{path}".':
        'В пути результата есть пробел, и он разделился на два аргумента. Возьмите его в кавычки: "{path}".',
    "ffmpeg not found. Install it (Windows: winget install ffmpeg) or put ffmpeg.exe next to the app.":
        "ffmpeg не найден. Установите его (Windows: winget install ffmpeg) или положите ffmpeg.exe рядом с программой.",
    "file not found: {path}": "файл не найден: {path}",
    "ffmpeg exited with code {code}:": "ffmpeg завершился с кодом {code}:",
    "the script finished but wrote nothing into {outdir}": "скрипт завершился, но ничего не записал в {outdir}",

    # --- core ---------------------------------------------------------------------------
    "protected by an anti-bot challenge": "защищён от ботов",
    "{n} dub only on unsupported players: {players}": (
        "{n} озвучка есть только в неподдерживаемых плеерах: {players}",
        "{n} озвучки есть только в неподдерживаемых плеерах: {players}",
        "{n} озвучек есть только в неподдерживаемых плеерах: {players}",
    ),
    "bad episode range: '{part}'": "неверный диапазон серий: «{part}»",
    "episode {ep} is not available": "серия {ep} недоступна",
    "player '{player}' is not supported yet": "плеер «{player}» пока не поддерживается",

    # --- help dialog --------------------------------------------------------------------
    "yummy-dl help": "Справка yummy-dl",
    "Quick start": "Быстрый старт",
    "API token": "Токен API",
    "Command line": "Командная строка",
    "About": "О программе",
    "✓ ffmpeg found, so every player works.": "✓ ffmpeg найден, все плееры работают.",
    "⚠ ffmpeg not found. Kodik episodes will be saved as <code>.ts</code>, and Aksor needs it. "
    "On Windows run <code>winget install ffmpeg</code> or put <code>ffmpeg.exe</code> next to the app.":
        "⚠ ffmpeg не найден. Серии из Kodik сохранятся в <code>.ts</code>, а для Aksor он обязателен. "
        "В Windows выполните <code>winget install ffmpeg</code> или положите <code>ffmpeg.exe</code> рядом с "
        "программой.",
    """
<h3>Downloading an episode</h3>
<ol>
<li><b>Search</b> for a title (Russian or English name) and press Enter.</li>
<li><b>Pick it</b> from the list on the left. Click the poster to see it full screen.</li>
<li>Choose the <b>dub</b>, the <b>player</b> (Auto picks the best one), the max <b>quality</b>
    and the <b>folder</b>.</li>
<li><b>Tick episodes</b>. Ones you already have are marked ✓.</li>
<li>Click <b>Download selected</b>. Progress shows in the queue at the bottom.</li>
</ol>
<h3>Good to know</h3>
<ul>
<li>Cancelling keeps partial files. Adding the episode again resumes it.</li>
<li>Double-click a finished row in the queue to open its folder.</li>
<li>Files are saved as <code>&lt;folder&gt;/&lt;Title&gt;/&lt;Title&gt; - E01 [Dub].mp4</code>.</li>
<li>Dubs only available on the Alloha player can't be downloaded (it uses anti-bot protection).</li>
<li>{ffmpeg_line}</li>
</ul>
<h3>Scripts</h3>
<p><b>Scripts → Manage scripts…</b> saves ffmpeg commands with a name and a comment, e.g. to convert
episodes for a TV or cut a long video into 10-minute parts. Run one from <b>Scripts → &lt;name&gt;</b> on files
or a folder, by right-clicking a finished download, or tick <i>Run automatically after each download</i>.
The converted file replaces the original.</p>
<p>Set up your <a href="#token">API token</a> once. It takes a minute.</p>
""": """
<h3>Как скачать серию</h3>
<ol>
<li><b>Найдите</b> аниме (по русскому или английскому названию) и нажмите Enter.</li>
<li><b>Выберите его</b> в списке слева. Нажмите на постер, чтобы открыть его на весь экран.</li>
<li>Выберите <b>озвучку</b>, <b>плеер</b> («Авто» выберет лучший), максимальное <b>качество</b>
    и <b>папку</b>.</li>
<li><b>Отметьте серии</b>. Уже скачанные помечены ✓.</li>
<li>Нажмите <b>Скачать выбранные</b>. Прогресс виден в очереди внизу.</li>
</ol>
<h3>Полезно знать</h3>
<ul>
<li>При отмене недокачанные файлы сохраняются. Если добавить серию снова, загрузка продолжится.</li>
<li>Двойной щелчок по завершённой строке очереди открывает её папку.</li>
<li>Файлы сохраняются как <code>&lt;папка&gt;/&lt;Название&gt;/&lt;Название&gt; - E01 [Озвучка].mp4</code>.</li>
<li>Озвучки, которые есть только в плеере Alloha, скачать нельзя (он защищён от ботов).</li>
<li>{ffmpeg_line}</li>
</ul>
<h3>Скрипты</h3>
<p><b>Скрипты → Управление скриптами…</b> хранит команды ffmpeg с названием и комментарием, например чтобы
перекодировать серии для телевизора или нарезать длинное видео на части по 10 минут. Запустите скрипт через
<b>Скрипты → &lt;название&gt;</b> для файлов или папки, правым щелчком по скачанной серии или отметьте
<i>Запускать автоматически после каждой загрузки</i>. Обработанный файл заменяет исходный.</p>
<p>Один раз настройте <a href="#token">токен API</a>. Это займёт минуту.</p>
""",
    """
<p>YummyAnime asks every app to identify itself with a free <b>application token</b>.
Downloads work without one today, but the API docs say it's required, so it's worth setting up.</p>
<ol>
<li>Log in (or register) at <a href="{site}">yummyani.me</a>.</li>
<li>Open <a href="{apps}">yummyani.me/dev/applications</a> and create an application.
    Any name and description will do.</li>
<li>Copy the application's <b>public token</b>.</li>
<li>Paste it below and click <b>Save token</b>.</li>
</ol>
""": """
<p>YummyAnime просит каждое приложение представляться бесплатным <b>токеном приложения</b>.
Сейчас загрузка работает и без него, но в документации API он обязателен, так что его стоит настроить.</p>
<ol>
<li>Войдите (или зарегистрируйтесь) на <a href="{site}">yummyani.me</a>.</li>
<li>Откройте <a href="{apps}">yummyani.me/dev/applications</a> и создайте приложение.
    Подойдут любые название и описание.</li>
<li>Скопируйте <b>публичный токен</b> приложения.</li>
<li>Вставьте его ниже и нажмите <b>Сохранить токен</b>.</li>
</ol>
""",
    "1. Open the applications page": "1. Открыть страницу приложений",
    "Paste your public token here": "Вставьте сюда публичный токен",
    "Paste": "Вставить",
    "Save token": "Сохранить токен",
    "The token is stored in <code>{path}</code> and sent as the <code>X-Application</code> header. "
    "The command-line tool uses the same setting. Instead of saving it here you can set the "
    "<code>{env}</code> environment variable, which takes priority.":
        "Токен хранится в <code>{path}</code> и отправляется в заголовке <code>X-Application</code>. "
        "Консольная версия использует ту же настройку. Вместо сохранения здесь можно задать переменную "
        "окружения <code>{env}</code>, она важнее.",
    "The command-line tool is <code>{cmd}</code>, in the same folder as this app: "
    "<code>{folder}</code>. Open a terminal there and run the commands below.":
        "Консольная версия — <code>{cmd}</code>, в той же папке, что и эта программа: "
        "<code>{folder}</code>. Откройте там терминал и выполняйте команды ниже.",
    "The command-line tool <code>{cmd}</code> is shipped in the release zip, next to <code>yummy-dl-gui.exe</code>.":
        "Консольная версия <code>{cmd}</code> лежит в архиве релиза рядом с <code>yummy-dl-gui.exe</code>.",
    "Run these in a terminal where yummy-dl is installed (your virtualenv).":
        "Выполняйте их в терминале, где установлен yummy-dl (в вашем virtualenv).",
    "Double-clicking it without arguments starts a guided mode that asks what to download step by step.":
        "Если запустить её двойным щелчком без аргументов, откроется пошаговый режим, который спросит, что скачать.",
    "Copy all": "Копировать всё",
    "Copied ✓": "Скопировано ✓",
    "Open terminal here": "Открыть терминал здесь",
    "Opens a Command Prompt in {folder}": "Открывает командную строку в {folder}",
    """
<p>Downloader for Russian-dubbed anime from <a href="{site}">YummyAnime</a>,
built on the official API (<a href="{docs}">docs</a>).</p>
<p>Supported players: CVH, Kodik, Aksor.</p>
<p>The YummyAnime API is <b>for personal use only</b>. Don't redistribute downloaded content.</p>
<p style='color:gray'>Settings file: <code>{path}</code></p>
""": """
<p>Загрузчик аниме с русской озвучкой с <a href="{site}">YummyAnime</a>
на основе официального API (<a href="{docs}">документация</a>).</p>
<p>Поддерживаемые плееры: CVH, Kodik, Aksor.</p>
<p>API YummyAnime — <b>только для личного использования</b>. Не распространяйте скачанное.</p>
<p style='color:gray'>Файл настроек: <code>{path}</code></p>
""",
    "✓ Using the token from the {env} environment variable (it overrides the saved one).":
        "✓ Используется токен из переменной окружения {env} (она важнее сохранённого).",
    "✓ A token is saved.": "✓ Токен сохранён.",
    "No token saved yet.": "Токен ещё не сохранён.",
    "⚠ That doesn't look like a token (it contains spaces). Copy just the token.":
        "⚠ Это не похоже на токен (в нём есть пробелы). Скопируйте только сам токен.",
    "Saved, you're all set.": "Сохранено, всё готово.",
    "Token removed.": "Токен удалён.",

    # --- help: command-line cheat sheet ------------------------------------------------
    "Find a title": "Найти аниме",
    "Show dubs, episodes and players for a title (id, alias or text)":
        "Показать озвучки, серии и плееры (id, alias или текст)",
    "Download: asks which dub and episodes if you leave them out": "Скачать: спросит озвучку и серии, если не указать",
    "Download non-interactively": "Скачать без вопросов",
    "part of the dub name": "часть названия озвучки",
    "e.g. 1-5,8  (default: all)": "например 1-5,8  (по умолчанию: все)",
    "max height: 1080, 720, 480, 360": "макс. высота: 1080, 720, 480, 360",
    "download folder": "папка для загрузок",
    "(default: auto)": "(по умолчанию: авто)",
    "parallel connections": "параллельные соединения",
    "Guided mode (what double-clicking {cmd} does)": "Пошаговый режим (то же, что двойной щелчок по {cmd})",
    "Settings": "Настройки",
    "auto, en or ru": "auto, en или ru",
    "Scripts (saved ffmpeg commands; create them in Scripts -> Manage scripts...)":
        "Скрипты (сохранённые команды ffmpeg; создаются в Скрипты -> Управление скриптами...)",
    "a folder or files; originals are replaced": "папка или файлы; исходники заменяются",
    "convert each new episode": "обработать каждую новую серию",
    "skip the auto-run script": "не запускать авто-скрипт",
    "Open this desktop app": "Открыть эту программу",
    "Built-in help for any command": "Встроенная справка по любой команде",

    # --- CLI ------------------------------------------------------------------------------
    "Arguments": "Аргументы",
    "Options": "Параметры",
    "Commands": "Команды",
    "[required]": "[обязательно]",
    "Download Russian-dubbed anime from YummyAnime. Personal use only.":
        "Скачивание аниме с русской озвучкой с YummyAnime. Только для личного использования.",
    "Manage settings (API token, defaults, language).": "Настройки (токен API, значения по умолчанию, язык).",
    "Run saved ffmpeg scripts on downloaded episodes (edit them in the GUI).":
        "Запуск сохранённых скриптов ffmpeg для скачанных серий (редактируются в программе).",
    "Error:": "Ошибка:",
    "nothing found for '{query}'": "по запросу «{query}» ничего не найдено",
    "Pick a title #": "Выберите № аниме",
    "Alias": "Alias",
    "Year": "Год",
    "Type": "Тип",
    "Episodes": "Серии",
    "Players": "Плееры",
    "Greyed out: {note}.": "Серым: {note}.",
    "Search titles by name.": "Поиск аниме по названию.",
    "How many results": "Сколько результатов показать",
    "Nothing found.": "Ничего не найдено.",
    "Show available dubs and episodes for a title.": "Показать доступные озвучки и серии.",
    "ID, alias, or search text": "ID, alias или текст для поиска",
    "alias": "alias",
    "No videos.": "Видео нет.",
    "Download episodes. Missing options are asked interactively.":
        "Скачать серии. Чего не хватает в параметрах — спросит.",
    "Dub name, e.g. 'AniLibria'": "Название озвучки, например 'AniLibria'",
    "e.g. 1-5,8 or all": "например 1-5,8 или all",
    "Max height: 360/480/720/1080": "Макс. высота: 360/480/720/1080",
    "Output directory": "Папка для сохранения",
    "Preferred player, e.g. kodik": "Предпочитаемый плеер, например kodik",
    "Parallel segment downloads": "Параллельные загрузки сегментов",
    "Run this saved script on each new episode (default: the auto-run script)":
        "Запустить этот скрипт для каждой новой серии (по умолчанию: авто-скрипт)",
    "Don't run the auto-run script": "Не запускать авто-скрипт",
    "no dubs with a supported player for this title": "у этого аниме нет озвучек в поддерживаемых плеерах",
    "dub '{dub}' not found": "озвучка «{dub}» не найдена",
    "dub '{dub}' is only on unsupported players": "озвучка «{dub}» есть только в неподдерживаемых плеерах",
    "Pick a dub #": "Выберите № озвучки",
    "Episodes ({range}), e.g. 1-3,5": "Серии ({range}), например 1-3,5",
    "nothing to download": "нечего скачивать",
    "Dub [cyan]{dub}[/cyan]": "Озвучка [cyan]{dub}[/cyan]",
    "{n} episode": ("{n} серия", "{n} серии", "{n} серий"),
    "up to {quality}p": "до {quality}p",
    "ffmpeg not found: Kodik episodes will be saved as .ts, Aksor episodes will fail.":
        "ffmpeg не найден: серии Kodik сохранятся в .ts, серии Aksor скачать не получится.",
    "After each episode: script [cyan]{name}[/cyan] (the original is replaced)":
        "После каждой серии: скрипт [cyan]{name}[/cyan] (исходный файл заменяется)",
    "skip (exists): {name}": "пропуск (уже есть): {name}",
    "Ep {ep}": "Серия {ep}",
    "saved": "сохранено",
    "episode {ep} failed:": "серия {ep} — ошибка:",
    "script": "скрипт",
    "{n} failed:": ("ошибок: {n} —", "ошибок: {n} —", "ошибок: {n} —"),
    "rerun to resume.": "запустите снова, чтобы продолжить.",
    "script failed": "скрипт не сработал",
    "on {name} (original kept):": "на {name} (исходный файл сохранён):",
    "converted": "обработано",
    "Show saved scripts.": "Показать сохранённые скрипты.",
    "No scripts yet. Create them in the desktop app (Scripts → Manage scripts…) or in {path}":
        "Скриптов пока нет. Создайте их в программе (Скрипты → Управление скриптами…) или в {path}",
    "Name": "Название",
    "Comment": "Комментарий",
    "Command": "Команда",
    "yes": "да",
    "Run a saved script on files or folders. Originals are deleted after a successful run.":
        "Запустить сохранённый скрипт для файлов или папок. Исходники удаляются после успешной обработки.",
    "Script name (or a unique part of it)": "Название скрипта (или его уникальная часть)",
    "Video files and/or folders of episodes": "Видеофайлы и/или папки с сериями",
    "Don't ask for confirmation": "Не спрашивать подтверждение",
    "ffmpeg not found (Windows: winget install ffmpeg)": "ffmpeg не найден (Windows: winget install ffmpeg)",
    "no video files found": "видеофайлы не найдены",
    "Script [cyan]{name}[/cyan]": "Скрипт [cyan]{name}[/cyan]",
    "{n} file:": ("{n} файл:", "{n} файла:", "{n} файлов:"),
    "Originals are deleted after each successful run. Continue?":
        "Исходники удаляются после каждой успешной обработки. Продолжить?",
    "{n} failed": ("ошибок: {n}", "ошибок: {n}", "ошибок: {n}"),
    "Save your YummyAnime application token (from yummyani.me/dev/applications).":
        "Сохранить токен приложения YummyAnime (с yummyani.me/dev/applications).",
    "Saved to {path}": "Сохранено в {path}",
    "Change default options.": "Изменить значения по умолчанию.",
    "Default download folder": "Папка для загрузок по умолчанию",
    "Default max quality": "Макс. качество по умолчанию",
    "Interface language: auto, en or ru": "Язык интерфейса: auto, en или ru",
    "unknown language '{lang}' (use auto, en or ru)": "неизвестный язык «{lang}» (доступны auto, en, ru)",
    "Print current settings.": "Показать текущие настройки.",
    "not set": "не задан",
    "system ({lang})": "как в системе ({lang})",
    "not found": "не найден",
    "Open the desktop window (needs: pip install 'yummy-dl[gui]').":
        "Открыть окно программы (нужно: pip install 'yummy-dl[gui]').",
    "Guided mode: search, pick a dub and episodes, download. Loops until you leave it empty.":
        "Пошаговый режим: поиск, выбор озвучки и серий, загрузка. Повторяется, пока не оставите строку пустой.",
    "downloads go to {path}": "загрузки сохраняются в {path}",
    "Change it with: yummy-dl config set --output-dir <folder>":
        "Изменить: yummy-dl config set --output-dir <папка>",
    "Title to search (empty to quit)": "Что ищем (пусто — выход)",
    "Press Enter to close...": "Нажмите Enter, чтобы закрыть...",
}
