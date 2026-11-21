from flask import Flask, render_template, request, jsonify
from flask_login import LoginManager, current_user
from config import Config
from models import db, Word, WordCategory, WordSynonym, Visit, UserVisit
from admin import admin_bp, create_admin
from models import Subscriber
from datetime import datetime, timedelta
import os
import re

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация базы данных
db.init_app(app)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin.login'


@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))


# Регистрация blueprint для админки
app.register_blueprint(admin_bp)

# СОЗДАНИЕ ТАБЛИЦ С ЗАЩИТОЙ ОТ ОШИБОК
with app.app_context():
    db.create_all()
    try:
        create_admin()
        print("✅ Admin check completed")
    except Exception as e:
        print(f"⚠️ Admin creation error: {e}")


# ============================================================
# АВТООПРЕДЕЛЕНИЕ ИМЕНИ DATETIME-ПОЛЯ В МОДЕЛЯХ
# ============================================================
def _find_date_field(model, preferred_names):
    """
    Возвращает имя первого найденного datetime-поля в модели.
    Приоритет — по списку preferred_names, иначе — любая колонка с 'datetime'.
    """
    for name in preferred_names:
        if hasattr(model, name):
            return name
    for col in model.__table__.columns:
        if 'datetime' in str(col.type).lower():
            return col.name
    return None


# ============================================================
# ОТСЛЕЖИВАНИЕ ПОСЕЩЕНИЙ (с автопоиском полей)
# ============================================================
@app.before_request
def track_visit():
    """Отслеживание посещений с автопоиском полей в моделях"""
    if (request.path.startswith('/static/') or
            request.path.startswith('/api/') or
            request.path.startswith('/admin/') or
            request.path == '/favicon.ico'):
        return

    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()

        user_agent = request.user_agent.string[:255] if request.user_agent.string else 'Unknown'

        # Автопоиск полей
        visit_date_field = _find_date_field(Visit, ['timestamp', 'visited_at', 'created_at', 'visit_date', 'date', 'time'])
        user_last_field = _find_date_field(UserVisit, ['last_visit', 'last_seen', 'updated_at', 'last_activity', 'last_visited'])
        user_first_field = _find_date_field(UserVisit, ['first_visit', 'created_at', 'registered_at', 'first_seen'])

        # 1. Записываем визит
        visit_data = {'ip_address': ip, 'user_agent': user_agent}
        if hasattr(Visit, 'path'):
            visit_data['path'] = request.path
        if visit_date_field:
            visit_data[visit_date_field] = datetime.utcnow()

        db.session.add(Visit(**visit_data))

        # 2. Обновляем/создаём уникального посетителя
        user_visit = UserVisit.query.filter_by(ip_address=ip).first()
        if user_visit:
            if user_last_field:
                setattr(user_visit, user_last_field, datetime.utcnow())
        else:
            user_data = {'ip_address': ip}
            if user_first_field:
                user_data[user_first_field] = datetime.utcnow()
            if user_last_field:
                user_data[user_last_field] = datetime.utcnow()
            db.session.add(UserVisit(**user_data))

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Ошибка при трекинге визита: {e}")


@app.route('/')
def index():
    """Главная страница"""
    try:
        words = Word.query.order_by(Word.word).limit(5).all()
        popular_words = [word.word for word in words] if words else ['tuproq', 'suv', "o'simlik", 'hosil', 'yer']
    except Exception:
        popular_words = ['tuproq', 'suv', "o'simlik", 'hosil', 'yer']
    return render_template('index.html', popular_words=popular_words)


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    results = []

    if query:
        try:
            words = Word.query.filter(
                Word.word.ilike(f'%{query.lower()}%'),
                ~Word.word.startswith('_category_placeholder_')
            ).all()

            def sort_words(word_obj):
                word_lower = word_obj.word.lower()
                query_lower = query.lower()
                if word_lower == query_lower:
                    return (0, word_lower)
                elif word_lower.startswith(query_lower):
                    return (1, word_lower)
                else:
                    return (2, word_lower)

            words = sorted(words, key=sort_words)

            for word in words:
                results.append({
                    'word': word.word,
                    'definition': word.definition[:200] + '...' if len(word.definition) > 200 else word.definition,
                    'sinonimlar': [syn.related_word for syn in word.synonyms[:3]],
                    'turkum': word.categories[0].category if word.categories.count() > 0 else ''
                })

        except Exception as e:
            print(f"Search error: {e}")
            results = []

    return render_template('search.html', query=query, results=results)


@app.route('/word/<word>')
def word_detail(word):
    try:
        db_word = Word.query.filter(Word.word.ilike(word)).first()
        if db_word:
            data = {
                'определение': db_word.definition,
                'translation_en': db_word.translation_en,
                'turkumi': [cat.category for cat in db_word.categories],
                'синонимы': [syn.related_word for syn in db_word.synonyms],
                'антонимы': [ant.related_word for ant in db_word.antonyms],
                'гиперонимы': [hyp.related_word for hyp in db_word.hyperonyms],
                'гипонимы': [hypo.related_word for hypo in db_word.hyponyms],
                'xolonim': [hol.related_word for hol in db_word.holonyms],
                'meronim': [mer.related_word for mer in db_word.meronyms],
                'omonim': [hom.related_word for hom in db_word.homonyms],
                'paronim': [par.related_word for par in db_word.paronyms],
                'qollanilishi': [area.area for area in db_word.usage_areas],
                'etimologiyasi': [db_word.etymology] if db_word.etymology else []
            }
            return render_template('word_detail.html', word=db_word.word, data=data)
    except Exception:
        pass
    return render_template('404.html'), 404


@app.route('/categories')
def categories():
    try:
        cats = db.session.query(WordCategory.category).distinct().order_by(WordCategory.category).all()
        categories = [cat[0] for cat in cats]
    except Exception:
        categories = []
    return render_template('categories.html', categories=categories)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').lower().strip()
    suggestions = []
    if query and len(query) >= 2:
        try:
            words = Word.query.filter(Word.word.ilike(f'%{query}%')).limit(10).all()
            suggestions = [word.word for word in words]
        except Exception:
            suggestions = []
    return jsonify(suggestions)


@app.route('/api/random-word')
def random_word():
    import random
    try:
        words = Word.query.all()
        if words:
            word = random.choice(words)
            return jsonify({
                'word': word.word,
                'definition': word.definition[:200] + '...' if len(word.definition) > 200 else word.definition,
                'categories': [cat.category for cat in word.categories]
            })
    except Exception:
        pass
    return jsonify({'word': None})


# ============================================================
# ОБНОВЛЁННЫЙ API СТАТИСТИКИ (с автопоиском полей)
# ============================================================
@app.route('/api/stats')
def get_stats():
    try:
        # === СТАТИСТИКА СЛОВ ===
        total_records = Word.query.filter(Word.word.notlike('_category_placeholder_%')).count()
        unique_words = db.session.query(Word.word).distinct().filter(
            Word.word.notlike('_category_placeholder_%')).count()
        total_categories = db.session.query(WordCategory.category).distinct().count()
        total_synonyms = WordSynonym.query.count()

        top_categories = [
            {"name": "Ot", "count": 4156},
            {"name": "Sifat", "count": 315},
            {"name": "Birikmali terminlar", "count": 383},
            {"name": "Fe'l", "count": 247},
            {"name": "Sifat/ot shaklidagi terminlar", "count": 22}
        ]

        # === СТАТИСТИКА ПОСЕЩЕНИЙ (автоопределение полей) ===
        visit_date_field = _find_date_field(Visit, ['timestamp', 'visited_at', 'created_at', 'visit_date', 'date', 'time'])
        user_last_field = _find_date_field(UserVisit, ['last_visit', 'last_seen', 'updated_at', 'last_activity', 'last_visited'])
        user_first_field = _find_date_field(UserVisit, ['first_visit', 'created_at', 'registered_at', 'first_seen'])

        # 1. Всего уникальных
        total_visitors = UserVisit.query.count()

        # 2. Сегодня (уникальные IP)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if visit_date_field:
            today_visitors = db.session.query(Visit.ip_address).filter(
                getattr(Visit, visit_date_field) >= today_start
            ).distinct().count()
        else:
            today_visitors = 0

        # 3. Активные за 24ч
        last_24h = datetime.utcnow() - timedelta(hours=24)
        if user_last_field:
            active_visitors = UserVisit.query.filter(
                getattr(UserVisit, user_last_field) >= last_24h
            ).count()
        else:
            active_visitors = 0

        # 4. Рост месяц/месяц
        first_day_this_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        first_day_last_month = (first_day_this_month - timedelta(days=1)).replace(day=1)

        growth = 0
        if user_first_field:
            users_this_month = UserVisit.query.filter(
                getattr(UserVisit, user_first_field) >= first_day_this_month
            ).count()
            users_last_month = UserVisit.query.filter(
                getattr(UserVisit, user_first_field) >= first_day_last_month,
                getattr(UserVisit, user_first_field) < first_day_this_month
            ).count()
            if users_last_month > 0:
                growth = round(((users_this_month - users_last_month) / users_last_month) * 100, 1)

        print(f"📊 API Stats: words={total_records}, visitors={total_visitors}, today={today_visitors}, active={active_visitors}")

    except Exception as e:
        print(f"❌ Error in /api/stats: {e}")
        total_records = 0
        unique_words = 0
        total_categories = 0
        total_synonyms = 0
        total_visitors = 0
        today_visitors = 0
        active_visitors = 0
        growth = 0
        top_categories = [{"name": "Ma'lumot yo'q", "count": 0}]

    return jsonify({
        'total_words': total_records,
        'unique_words': unique_words,
        'total_categories': total_categories,
        'total_synonyms': total_synonyms,
        'total_visitors': total_visitors,
        'today_visitors': today_visitors,
        'active_visitors': active_visitors,
        'growth': growth,
        'top_categories': top_categories
    })


@app.route('/stats/agriculture')
def agriculture_stats():
    """Statistika sahifasi - 16 ta vkladka"""
    from models import WordUsageArea

    tab = request.args.get('tab', 'general')

    # ========== DEHQONCHILIK (O'SIMLIKSHUNOSLIK) QUYI TARMOQLARI ==========
    if tab == 'agriculture':
        agriculture_sub_industries = {
            "Donchilik (gallachilik)": ["дон", "ғалла", "буғдой", "арпа", "шоли", "жувори", "маккажўхори", "don",
                                        "galla", "bug'doy", "arpa"],
            "Sabzavotchilik": ["сабзавот", "сабзавотчилик", "помидор", "бодиринг", "пиёз", "саримсоқ", "сабзи",
                               "картошка", "sabzavot"],
            "Polizchilik": ["полиз", "тарвуз", "қовун", "овун", "полизчилик", "tarvuz", "qovun"],
            "Texnik ekinlar (paxta, yog'li va tolali ekinlar)": ["пахта", "пахтачилик", "кунгибоқар", "зиғир", "каноп",
                                                                 "paxta", "kungaboqar", "zig'ir"],
            "Em-xashak ekinlari": ["ем-хашак", "беда", "севуш", "жўхори", "судан", "em-xashak", "beda", "sevush",
                                   "yem-xashak"],
            "Dorivor va efir-moyli ekinlar": ["доривор", "эфир-мойли", "яхтак", "ral", "dorivor", "efir-moyli",
                                              "yalpiz", "romashka"],
            "Urug'chilik va selektsiya": ["уруғчилик", "селекция", "уруғ", "нав", "уруғчи", "urug'chilik", "selektsiya",
                                          "urug'", "nav"],
            "Agrotexnika, sug'orish va agrotizimlar": ["агротехника", "суғориш", "агротизим", "агротехнология",
                                                       "agrotexnika", "sug'orish", "agrotizim"]
        }

        stats = []
        total = 0

        for sub_name, keywords in agriculture_sub_industries.items():
            word_ids = set()
            for kw in keywords:
                areas = WordUsageArea.query.filter(
                    WordUsageArea.area.ilike(f"%{kw}%")
                ).all()
                for area in areas:
                    word_ids.add(area.word_id)

            count = len(word_ids)
            total += count
            stats.append({
                "name": sub_name,
                "count": count
            })

        for stat in stats:
            stat["percentage"] = round(stat["count"] / total * 100, 1) if total > 0 else 0

        stats.sort(key=lambda x: x["count"], reverse=True)

        return render_template('agriculture_stats.html',
                               stats=stats,
                               total=total,
                               active_tab='agriculture')

    # ========== BOG'DORCHILIK QUYI TARMOQLARI ==========
    elif tab == 'gardening':
        gardening_sub_industries = {
            "Urug'li mevachilik (olma, nok, behi va boshqalar)": ["олма", "нок", "беҳи", "урғли", "olma", "nok",
                                                                  "behi"],
            "Danakli mevachilik (o'rik, shaftoli, olcha, gilos va boshqalar)": ["ўрик", "шафтоли", "олча", "гилос",
                                                                                "o'rik", "shaftoli", "olcha", "gilos"],
            "Uzumchilik (vinogradarstvo)": ["узум", "виноград", "ток", "uzum", "vinograd", "tok"],
            "Rezavor-mevachilik": ["резавор", "малина", "қорағат", "клубника", "rezavor", "malina", "qorag'at",
                                   "klubnika"],
            "Yong'oqmevachilik (bodom, yong'oq, pista va boshqalar)": ["бодом", "ёнғоқ", "писта", "bodom", "yong'oq",
                                                                       "pista"],
            "Tsitrus va subtropik mevachilik": ["цитрус", "лимон", "апельсин", "мандарин", "sitrus", "limon", "apelsin",
                                                "mandarin"],
            "Manzarali (dekorativ) bog'dorchilik": ["манзарали", "декоратив", "гул", "da'raxt", "dekorativ", "gul"]
        }

        stats = []
        total = 0

        for sub_name, keywords in gardening_sub_industries.items():
            word_ids = set()
            for kw in keywords:
                areas = WordUsageArea.query.filter(
                    WordUsageArea.area.ilike(f"%{kw}%")
                ).all()
                for area in areas:
                    word_ids.add(area.word_id)

            count = len(word_ids)
            total += count
            stats.append({
                "name": sub_name,
                "count": count
            })

        for stat in stats:
            stat["percentage"] = round(stat["count"] / total * 100, 1) if total > 0 else 0

        stats.sort(key=lambda x: x["count"], reverse=True)

        return render_template('agriculture_stats.html',
                               stats=stats,
                               total=total,
                               active_tab='gardening')

    # ========== CHORVACHILIK QUYI TARMOQLARI ==========
    elif tab == 'livestock':
        livestock_sub_industries = {
            "Qoramolchilik": ["қорамол", "сигир", "буқа", "мол", "қорамолчилик", "sigir", "buqa", "g'unajin", "sog'in",
                              "buzoq", "qoramol", "qoramolchilik"],
            "Qo'ychilik": ["қўй", "қочқор", "қўзи", "жун", "қўйчилик", "qo'y", "qo'‘y", "surgich", "qo'zichoq", "teri"],
            "Parrandachilik": ["товуқ", "парранда", "тухум", "бройлер", "паррандачилик", "tovuq", "jo'ja", "kurka",
                               "o'rdak", "g'oz"],
            "Yilqichilik": ["от", "бия", "тулов", "йилқи", "отчилик", "yilqi", "ot", "toychoq", "quloqin", "noxo'ta"],
            "Echkichilik": ["эчки", "улоқ", "эчкичилик", "echki", "taka", "echkichilik", "echkichi"],
            "Cho'chqachilik": ["чўчқа", "чўчкачилик", "cho'‘chqa", "cho'chqa", "cho'chqachilik", "cho'chqa go'shti"],
            "Ipakchilik (pillachilik)": ["ипак", "пилла", "тут ипак курти", "ипакчилик", "ipak", "pillachilik",
                                         "pillaxona"],
            "Asalarichilik": ["асалари", "ари", "асал", "асаларичилик", "asalari", "asalarichilik", "asal", "ari",
                              "asari uyasi"],
            "Baliqchilik va akvakultura": ["балиқ", "балиқчилик", "аквакультура", "baliq", "baliqchilik", "akvakultura"]
        }

        stats = []
        total = 0

        for sub_name, keywords in livestock_sub_industries.items():
            word_ids = set()
            for kw in keywords:
                areas = WordUsageArea.query.filter(
                    WordUsageArea.area.ilike(f"%{kw}%")
                ).all()
                for area in areas:
                    word_ids.add(area.word_id)

            count = len(word_ids)
            total += count
            stats.append({
                "name": sub_name,
                "count": count
            })

        for stat in stats:
            stat["percentage"] = round(stat["count"] / total * 100, 1) if total > 0 else 0

        stats.sort(key=lambda x: x["count"], reverse=True)

        return render_template('agriculture_stats.html',
                               stats=stats,
                               total=total,
                               active_tab='livestock')

    # ========== SO'Z TURKUMLARI STATISTIKASI ==========
    elif tab == 'wordtypes':
        wordtypes_stats = [
            {"name": "Ot", "count": 4156, "percentage": 80.92},
            {"name": "Sifat", "count": 315, "percentage": 6.13},
            {"name": "Fe'l", "count": 247, "percentage": 4.81},
            {"name": "Birikmali terminlar", "count": 383, "percentage": 7.46},
            {"name": "Sifat/ot shaklidagi terminlar", "count": 22, "percentage": 0.43},
            {"name": "Ibora va frazeologik birliklar", "count": 5, "percentage": 0.10},
            {"name": "Ravish", "count": 4, "percentage": 0.08},
            {"name": "Yordamchi birliklar", "count": 2, "percentage": 0.04},
            {"name": "Undov", "count": 2, "percentage": 0.04}
        ]

        return render_template('agriculture_stats.html',
                               stats=wordtypes_stats,
                               total=5136,
                               active_tab='wordtypes')

    # ========== TERMIN TURLARI (SO'Z TARKIBI) ==========
    elif tab == 'termtypes':
        termtypes_stats = [
            {"name": "Tub (sodda) so'zlar", "count": 2112, "percentage": 41.1},
            {"name": "Yasama so'zlar (ildiz + affiks)", "count": 1305, "percentage": 25.4},
            {"name": "Qo'shma so'zlar", "count": 729, "percentage": 14.2},
            {"name": "Birikmali terminlar (so'z birikmalari)", "count": 770, "percentage": 15.0},
            {"name": "O'zlashma terminlar (lotin, grek, arab va boshqalar)", "count": 200, "percentage": 3.9},
            {"name": "Qisqartma, frazeologik va boshqa birliklar", "count": 20, "percentage": 0.4}
        ]

        return render_template('agriculture_stats.html',
                               stats=termtypes_stats,
                               total=5136,
                               active_tab='termtypes')

    # ========== GIPERONIM GURUHLARI (SOHALAR) ==========
    elif tab == 'hyperonyms':
        hyperonym_stats = [
            {
                "name": "🔬 Biologiya va ekologiya (o'simlik, hayvon, biologik jarayon, flora, fauna, gen, DNK va boshqalar)",
                "count": 1495, "percentage": 29.1},
            {
                "name": "🌾 Qishloq xo'jaligi va dehqonchilik (ekin, agrotexnik jarayon, sug'orish, o'g'it, bog'dorchilik, polizchilik va boshqalar)",
                "count": 1264, "percentage": 24.6},
            {
                "name": "🐄 Chorvachilik va veterinariya (qoramol, qo'y, parranda, kasallik, zot, reproduktiv jarayon va boshqalar)",
                "count": 852, "percentage": 16.6},
            {
                "name": "🌱 Tuproqshunoslik, irrigatsiya va melioratsiya (tuproq turi, yer maydoni, gidroinshoot, melioratsiya va boshqalar)",
                "count": 534, "percentage": 10.4},
            {
                "name": "💰 Iqtisodiyot va boshqaruv (iqtisodiy jarayon, bozor, moliya, mulk, boshqaruv tizimi va boshqalar)",
                "count": 447, "percentage": 8.7},
            {"name": "🔧 Texnika va texnologiya (qurilma, mexanizm, mashina, texnologik jarayon, uskuna va boshqalar)",
             "count": 370, "percentage": 7.2},
            {
                "name": "👥 Ijtimoiy-gumanitar va huquqiy sohalar (ijtimoiy holat, kasb, huquqiy hujjat, ta'lim va boshqalar)",
                "count": 174, "percentage": 3.4}
        ]

        return render_template('agriculture_stats.html',
                               stats=hyperonym_stats,
                               total=5136,
                               active_tab='hyperonyms')

    # ========== GIPONIM GURUHLARI (SOHAVIY GURUHLAR) ==========
    elif tab == 'hyponyms':
        hyponym_stats = [
            {"name": "🌿 O'simlikshunoslik va botanika (o'simlik turi, nav, daraxt, buta, gul, urug', morfologiya)",
             "count": 1463, "percentage": 28.5},
            {"name": "🌾 Qishloq xo'jaligi va dehqonchilik (ekin turlari, agrotadbirlar, sug'orish, ekish, hosil)",
             "count": 1171, "percentage": 22.8},
            {"name": "🐄 Chorvachilik va zootexniya (zotlar, hayvon turlari, mahsulot, boqish)", "count": 996,
             "percentage": 19.4},
            {"name": "🌍 Ekologiya va tabiiy muhit (iqlim, zona, landshaft, tabiiy omillar)", "count": 632,
             "percentage": 12.3},
            {"name": "🏥 Veterinariya va tibbiy-biologik atamalar (kasallik, fiziologiya, patologiya)", "count": 421,
             "percentage": 8.2},
            {"name": "🔧 Agrotexnika va texnologiya (mashina, qurilma, mexanizatsiya, jihoz)", "count": 287,
             "percentage": 5.6},
            {"name": "📊 Iqtisodiy-tashkiliy va ijtimoiy tushunchalar (bozor, boshqaruv, mulk, mehnat)", "count": 166,
             "percentage": 3.2}
        ]

        return render_template('agriculture_stats.html',
                               stats=hyponym_stats,
                               total=5136,
                               active_tab='hyponyms')

    # ========== HOLONIM GURUHLARI (BUTUN TUSHUNCHALAR) ==========
    elif tab == 'holonyms':
        holonym_stats = [
            {"name": "🧬 Biologik tizimlar (organizm, to'qima, hujayra, genetik tizim, fiziologik tizimlar)",
             "count": 1457, "percentage": 28.4},
            {"name": "🌍 Ekologik va tabiiy tizimlar (ekotizim, biosfera, landshaft, iqlim, muhit)", "count": 1032,
             "percentage": 20.1},
            {
                "name": "🌾 Qishloq xo'jaligi va agrar tizimlar (dehqonchilik, chorvachilik, agrosanoat majmuasi, agrotizim)",
                "count": 1217, "percentage": 23.7},
            {"name": "💰 Iqtisodiy va ijtimoiy tizimlar (milliy iqtisodiyot, bozor, boshqaruv, jamiyat)", "count": 668,
             "percentage": 13.0},
            {
                "name": "🔧 Texnika, texnologiya va ishlab chiqarish tizimlari (mashinalar tizimi, texnologiya, infratuzilma)",
                "count": 452, "percentage": 8.8},
            {"name": "📚 Ilmiy va ta'lim tizimlari (fanlar tizimi, ilmiy tadqiqot, terminologik tizim)", "count": 310,
             "percentage": 6.0}
        ]

        return render_template('agriculture_stats.html',
                               stats=holonym_stats,
                               total=5136,
                               active_tab='holonyms')

    # ========== MERONIM GURUHLARI (QISM TUSHUNCHALAR) ==========
    elif tab == 'meronyms':
        meronym_stats = [
            {
                "name": "🧬 Biologik va anatomik qismlar (barg, poya, ildiz, organ, hujayra, to'qima, suyak, mushak va boshqalar)",
                "count": 1829, "percentage": 35.6},
            {
                "name": "🌿 O'simlik morfologiyasi va reproduktiv qismlar (gul, meva, urug', danak, po'stloq, shox, kurtak va boshqalar)",
                "count": 1212, "percentage": 23.6},
            {
                "name": "🐄 Chorvachilik va hayvon tanasi qismlari (yelin, tuyoq, qanot, tumshuq, teri, jun, ichki a'zolar)",
                "count": 729, "percentage": 14.2},
            {
                "name": "🌱 Tuproq va tabiiy muhit qatlamlari (tuproq qatlami, gumus, namlik, suv qatlamlari, qum, shag'al)",
                "count": 514, "percentage": 10.0},
            {"name": "🔧 Texnika va mexanik tizim qismlari (mexanizm, detal, val, g'ildirak, filtr, nozul, sensor)",
             "count": 457, "percentage": 8.9},
            {"name": "⚗️ Kimyoviy va biokimyoviy tarkibiy qismlar (molekula, ion, element, gen, DNK, oqsil, ferment)",
             "count": 282, "percentage": 5.5},
            {"name": "📊 Iqtisodiy-tashkiliy qismlar (bo'lim, band, ulush, mablag', hujjat, jarayon bosqichi)",
             "count": 113, "percentage": 2.2}
        ]

        return render_template('agriculture_stats.html',
                               stats=meronym_stats,
                               total=5136,
                               active_tab='meronyms')

    # ========== SINONIM STATISTIKASI ==========
    elif tab == 'synonyms':
        synonym_stats = [
            {"name": "🔄 Sinonimi mavjud terminlar", "count": 3703, "percentage": 72.1},
            {"name": "❌ Sinonimi berilmagan terminlar", "count": 1433, "percentage": 27.9}
        ]

        return render_template('agriculture_stats.html',
                               stats=synonym_stats,
                               total=5136,
                               active_tab='synonyms')

    # ========== ANTONIM STATISTIKASI ==========
    elif tab == 'antonyms':
        antonym_stats = [
            {"name": "⚔️ Aniq antonimi mavjud (masalan: normal – buzilgan, madaniy – yovvoyi, sog'lom – kasal)",
             "count": 1324, "percentage": 25.8},
            {"name": "🔄 Shartli / kontekstual antonim (ma'nosi vaziyatga bog'liq)", "count": 766, "percentage": 14.9},
            {"name": "❌ Antonimi berilmagan (—, yo'q)", "count": 3046, "percentage": 59.3}
        ]

        return render_template('agriculture_stats.html',
                               stats=antonym_stats,
                               total=5136,
                               active_tab='antonyms')

    # ========== OMONIM STATISTIKASI ==========
    elif tab == 'homonyms':
        homonym_stats = [
            {"name": "🔤 Aniq omonim mavjud (bir xil shakl – semantik jihatdan bog'liq bo'lmagan turli ma'nolar)",
             "count": 9, "percentage": 0.2},
            {"name": "🌐 Fanlararo omonim", "count": 0, "percentage": 0.0},
            {"name": "📖 Polisemiya (ko'p ma'nolilik), lekin omonim emas", "count": 0, "percentage": 0.0},
            {"name": "❌ Omonimi mavjud emas", "count": 5127, "percentage": 99.8}
        ]

        return render_template('agriculture_stats.html',
                               stats=homonym_stats,
                               total=5136,
                               active_tab='homonyms')

    # ========== OMONIMIYA MANBALARI ==========
    elif tab == 'homonym_sources':
        homonym_source_stats = [
            {"name": "📖 Umumiy til ma'nosi ↔ terminologik ma'no o'rtasidagi omonimiya", "count": 4, "percentage": 44.4},
            {"name": "🔬 Fanlararo omonimiya (biologiya, iqtisod, texnika va boshqa sohalar)", "count": 1,
             "percentage": 11.1},
            {"name": "🎭 Ko'chma yoki badiiy (metaforik, metonimik) ma'no asosida shakllangan omonimiya", "count": 2,
             "percentage": 22.2},
            {"name": "🏷️ Atama va nomlar to'qnashuvi (zoonim, fitonim va boshqalar)", "count": 2, "percentage": 22.2},
            {"name": "📌 Boshqa holatlar", "count": 0, "percentage": 0.0}
        ]

        return render_template('agriculture_stats.html',
                               stats=homonym_source_stats,
                               total=9,
                               active_tab='homonym_sources')

    # ========== PARONIM STATISTIKASI ==========
    elif tab == 'paronyms':
        paronym_stats = [
            {"name": "🎯 Aniq paronim juftligi mavjud (ma'nosi farq qiluvchi, lekin talaffuzi yaqin mustaqil terminlar)",
             "count": 52, "percentage": 1.0},
            {"name": "🔊 Fonetik-grafik yaqin paronimlar (imlo, talaffuz yoki transliteratsiya farqi bilan)",
             "count": 16, "percentage": 0.3},
            {"name": "🌐 Fanlararo paronimiya (turli fan sohalarida qo'llanuvchi, shaklan yaqin terminlar)", "count": 4,
             "percentage": 0.1},
            {"name": "❌ Paronimi mavjud emas", "count": 5064, "percentage": 98.6}
        ]

        return render_template('agriculture_stats.html',
                               stats=paronym_stats,
                               total=5136,
                               active_tab='paronyms')

    # ========== OBUNACHILAR STATISTIKASI ==========
    elif tab == 'subscribers':
        from sqlalchemy import func

        total_subs = Subscriber.query.count()
        active_subs = Subscriber.query.filter_by(is_active=True).count()

        by_source_rows = (db.session.query(
            Subscriber.source, func.count(Subscriber.id))
                          .filter(Subscriber.is_active == True)
                          .group_by(Subscriber.source)
                          .order_by(func.count(Subscriber.id).desc())
                          .all())

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        last_30 = Subscriber.query.filter(
            Subscriber.subscribed_at >= thirty_days_ago
        ).count()

        first_day = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month = Subscriber.query.filter(
            Subscriber.subscribed_at >= first_day
        ).count()

        subscribers_data = {
            'total': total_subs,
            'active': active_subs,
            'inactive': total_subs - active_subs,
            'last_30': last_30,
            'this_month': this_month,
            'by_source': [
                {'source': s or 'website', 'count': c,
                 'percent': round(c / active_subs * 100, 1) if active_subs else 0}
                for s, c in by_source_rows
            ],
        }

        return render_template('agriculture_stats.html',
                               stats=[],
                               total=active_subs,
                               active_tab='subscribers',
                               subscribers=subscribers_data)

    # ========== UMUMIY QISHLOQ XO'JALIGI YO'NALISHLARI ==========
    else:
        industries = {
            "O‘simlikshunoslik, dehqonchilik, agronomiya": [
                "ўсимлик", "ўсимликшунослик", "деҳқончилик", "дехқончилик", "dehqonchilik",
                "агрономия", "agronomiya", "ғалла", "пахта", "дон", "кунгибоқар",
                "сабзавот", "мева", "полиз", "богдорчилик", "ekinshunoslik"
            ],
            "Chorvachilik, zootexniya, parrandachilik": [
                "чорвачилик", "чорва", "chorvachilik", "зоотехния", "zootexniya",
                "паррандачилик", "parrandachilik", "парранда", "мол", "қорамол",
                "қўй", "эчки", "от", "yilqichilik", "chavandozlik"
            ],
            "Tuproqshunoslik, agrokimyo, o‘g‘itlash": [
                "тупроқшунослик", "тупроқ", "tuproq", "агрокимё", "agrokimyo",
                "ўғитлаш", "ўғит", "o‘g‘it", "o'g'it", "gumus", "эрозия"
            ],
            "Suv xo‘jaligi, irrigatsiya, melioratsiya": [
                "сув хўжалиги", "сув", "suv", "ирригация", "irrigatsiya",
                "мелиорация", "melioratsiya", "суғориш", "sug‘orish", "sug'orish",
                "канол", "ариқ", "заҳ", "шўрланиш"
            ],
            "O‘simlik va hayvon kasalliklari, himoya": [
                "касаллик", "ўсимлик касаллиги", "ҳайвон касаллиги", "kasallik",
                "ҳимоя", "himoya", "зараркунанда", "карантин", "пестицид",
                "гербицид", "фунгицид", "инсектицид", "veterinariya", "farmakologiya"
            ],
            "Mexanizatsiya, texnika, texnologiya": [
                "механизация", "mexanizatsiya", "техника", "texnika", "технология",
                "texnologiya", "трактор", "trakтор", "комбайн", "kombayn",
                "плуг", "агрегат", "agregat", "q/x texnikasi"
            ],
            "Bog‘dorchilik (meva-sabzavotchilik, rezavorchilik, uzumchilik)": [
                "богдорчилик", "bog‘dorchilik", "bog'dorchilik", "бог", "bog'",
                "мевачилик", "mevachilik", "сабзавотчилик", "sabzavotchilik",
                "резаворчилик", "rezavorchilik", "узумчилик", "uzumchilik", "узум",
                "ток", "ғўра", "олма", "gulchilik", "plantatsiya"
            ],
            "Agrar iqtisodiyot, boshqaruv va bozor munosabatlari": [
                "аграр иқтисодиёт", "agrar iqtisodiyot", "иқтисодиёт", "iqtisodiyot",
                "бошқарув", "boshqaruv", "бозор", "bozor", "маркетинг", "marketing",
                "савдо", "savdo", "экспорт", "eksport", "импорт", "import",
                "субсидия", "kredit", "фермер", "dehqon", "agromenejment"
            ],
            "Ekologiya, biologiya va biotexnologiya": [
                "экология", "ekologiya", "биология", "biologiya", "биотехнология",
                "biotexnologiya", "генетика", "genetika", "селекция", "selektsiya",
                "биохимия", "bioximiya", "экосистема", "ekotizim", "botanika",
                "zoologiya", "anatomiya", "zoogigiyena", "geografiya"
            ]
        }

        stats = []
        total = 0

        for industry_name, keywords in industries.items():
            word_ids = set()
            for keyword in keywords:
                areas = WordUsageArea.query.filter(
                    WordUsageArea.area.ilike(f"%{keyword}%")
                ).all()
                for area in areas:
                    word_ids.add(area.word_id)

            count = len(word_ids)
            total += count
            stats.append({
                "name": industry_name,
                "count": count
            })

        for stat in stats:
            stat["percentage"] = round(stat["count"] / total * 100, 1) if total > 0 else 0

        stats.sort(key=lambda x: x["count"], reverse=True)

        return render_template('agriculture_stats.html',
                               stats=stats,
                               total=total,
                               active_tab='general')


@app.route('/api/semantic-network/<word>')
def semantic_network(word):
    try:
        db_word = Word.query.filter(Word.word.ilike(word)).first()
        if db_word:
            nodes = [{'id': db_word.word, 'type': 'main'}]
            links = []

            relation_types = [
                ('synonyms', 'синоним', '#4CAF50'),
                ('antonyms', 'антоним', '#f44336'),
                ('hyperonyms', 'гипероним', '#FF9800'),
                ('hyponyms', 'гипоним', '#2196F3'),
                ('holonyms', 'холоним', '#9C27B0'),
                ('meronyms', 'мероним', '#FF6B6B'),
                ('homonyms', 'омоним', '#00BCD4'),
                ('paronyms', 'пароним', '#FFC107'),
            ]

            for attr_name, rel_type, color in relation_types:
                relations = getattr(db_word, attr_name, [])
                for rel in relations:
                    nodes.append({'id': rel.related_word, 'type': rel_type})
                    links.append({
                        'source': db_word.word,
                        'target': rel.related_word,
                        'type': rel_type,
                        'color': color
                    })

            for area in db_word.usage_areas:
                nodes.append({'id': f"[{area.area}]", 'type': 'qollanilishi', 'is_usage': True})
                links.append({
                    'source': db_word.word,
                    'target': f"[{area.area}]",
                    'type': 'qollanilishi',
                    'color': '#795548'
                })

            unique_nodes = []
            seen = set()
            for node in nodes:
                if node['id'] not in seen:
                    seen.add(node['id'])
                    unique_nodes.append(node)

            return jsonify({
                'focus': db_word.word,
                'nodes': unique_nodes,
                'links': links
            })
    except Exception as e:
        print(f"Error: {e}")
        pass
    return jsonify({'error': 'So\'z topilmadi'}), 404


@app.context_processor
def inject_globals():
    from models import Word, WordCategory, WordSynonym

    try:
        total_words = Word.query.count()
        total_categories = db.session.query(WordCategory.category).distinct().count()
        total_synonyms = WordSynonym.query.count()
    except Exception:
        total_words = total_categories = total_synonyms = 0

    return dict(
        is_admin=False,
        current_user=None,
        total_words=total_words,
        total_categories=total_categories,
        total_synonyms=total_synonyms
    )


@app.route('/debug/usage-check')
def debug_usage_check():
    from models import WordUsageArea, Word

    total = WordUsageArea.query.count()
    areas = WordUsageArea.query.limit(10).all()
    data = []
    for a in areas:
        word = Word.query.get(a.word_id)
        data.append({
            'word_id': a.word_id,
            'word': word.word if word else 'Unknown',
            'area': a.area
        })

    return jsonify({
        'total': total,
        'sample': data,
        'all_areas': list(set([a.area for a in WordUsageArea.query.all()]))
    })


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500


@app.template_filter('numberformat')
def numberformat_filter(value):
    try:
        return f"{int(value):,}".replace(",", " ")
    except (ValueError, TypeError):
        return value


# ============================================================
# API ПОДПИСКИ
# ============================================================

@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        name = (data.get('name') or '').strip()

        if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return jsonify({'success': False, 'error': "Email formati noto'g'ri"}), 400

        existing = Subscriber.query.filter_by(email=email).first()

        if existing:
            if existing.is_active:
                return jsonify({'success': False,
                                'error': "Bu email allaqachon obuna bo'lgan"}), 409
            existing.is_active = True
            existing.subscribed_at = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'success': True,
                'message': "Obuna qayta tiklandi!",
                'count': Subscriber.query.filter_by(is_active=True).count()
            })

        sub = Subscriber(
            email=email,
            name=name or None,
            source=data.get('source', 'website'),
            ip_address=request.remote_addr,
        )
        db.session.add(sub)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': "Muvaffaqiyatli obuna bo'ldingiz!",
            'count': Subscriber.query.filter_by(is_active=True).count()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/unsubscribe', methods=['POST'])
def api_unsubscribe():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    sub = Subscriber.query.filter_by(email=email, is_active=True).first()
    if not sub:
        return jsonify({'success': False, 'error': "Obuna topilmadi"}), 404
    sub.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': "Obunadan chiqdingiz"})


@app.route('/api/subscribers/count')
def api_subscribers_count():
    return jsonify({
        'active': Subscriber.query.filter_by(is_active=True).count(),
        'total': Subscriber.query.count(),
    })


@app.route('/api/subscribers')
def api_subscribers_list():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    pag = (Subscriber.query
           .order_by(Subscriber.subscribed_at.desc())
           .paginate(page=page, per_page=per_page, error_out=False))

    return jsonify({
        'total': pag.total,
        'active': Subscriber.query.filter_by(is_active=True).count(),
        'page': page,
        'pages': pag.pages,
        'items': [s.to_dict() for s in pag.items],
    })


if __name__ == '__main__':
    app.run(debug=True)