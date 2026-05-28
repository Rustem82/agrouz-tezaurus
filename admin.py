from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Word, WordCategory, WordSynonym, WordAntonym, WordHyperonym, WordHyponym, WordHolonym, \
    WordMeronym, WordHomonym, WordParonym, WordUsageArea
from functools import wraps
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ЗАЩИТЫ ОТ ДУБЛИКАТОВ ==========

def add_unique_relation(word_id, relation_model, value, value_field='related_word'):
    """Добавляет связь только если она еще не существует"""
    if not value or not value.strip():
        return

    value = value.strip()

    # Проверяем, существует ли уже такая связь
    existing = relation_model.query.filter_by(
        word_id=word_id,
        **{value_field: value}
    ).first()

    if not existing:
        db.session.add(relation_model(word_id=word_id, **{value_field: value}))


def add_unique_categories(word_id, categories):
    """Добавляет категории без дубликатов"""
    added = set()
    for cat in categories:
        cat = cat.strip()
        if cat and cat not in added:
            added.add(cat)
            existing = WordCategory.query.filter_by(word_id=word_id, category=cat).first()
            if not existing:
                db.session.add(WordCategory(word_id=word_id, category=cat))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Bu sahifaga kirish uchun admin huquqlari kerak', 'danger')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)

    return decorated_function


# Kontekst protsessorlari
@admin_bp.context_processor
def inject_now():
    return {'now': datetime.now}


@admin_bp.context_processor
def inject_admin_data():
    return {
        'words_count': Word.query.count()
    }


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Xush kelibsiz!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Login yoki parol noto\'g\'ri', 'danger')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Tizimdan chiqdingiz', 'info')
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@admin_required
def dashboard():
    # Asosiy statistika
    words_count = Word.query.count()
    categories_count = db.session.query(WordCategory.category).distinct().count()

    # Sinonimlar soni
    total_synonyms = WordSynonym.query.count()

    # Kategoriyalar bo'yicha statistika
    categories = db.session.query(WordCategory.category).distinct().order_by(WordCategory.category).all()
    category_stats = []

    for cat in categories:
        cat_name = cat[0]
        count = WordCategory.query.filter_by(category=cat_name).count()
        percentage = (count / words_count * 100) if words_count > 0 else 0
        category_stats.append({
            'name': cat_name,
            'count': count,
            'percentage': round(percentage, 1)
        })

    # Oxirgi qo'shilgan so'zlar
    recent_words = Word.query.order_by(Word.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                           words_count=words_count,
                           categories_count=categories_count,
                           total_synonyms=total_synonyms,
                           category_stats=category_stats,
                           recent_words=recent_words)


@admin_bp.route('/words')
@admin_required
def words():
    page = request.args.get('page', 1, type=int)
    words = Word.query.order_by(Word.word).paginate(page=page, per_page=20)
    return render_template('admin/words.html', words=words)


@admin_bp.route('/words/add', methods=['GET', 'POST'])
@admin_required
def add_word():
    if request.method == 'POST':
        word_text = request.form.get('word', '').strip().lower()

        # Tekshirish: so'z mavjudmi?
        existing = Word.query.filter_by(word=word_text).first()
        if existing:
            flash('Bu so\'z allaqachon mavjud', 'danger')
            return redirect(url_for('admin.add_word'))

        # Yangi so'z yaratish
        word = Word(
            word=word_text,
            definition=request.form.get('definition', ''),
            etymology=request.form.get('etymology', ''),
            translation_en=request.form.get('translation_en', '')
        )
        db.session.add(word)
        db.session.flush()  # ID olish uchun

        # Kategoriyalar - YANGI (без дубликатов)
        add_unique_categories(word.id, request.form.getlist('categories[]'))

        # Sinonimlar - YANGI (без дубликатов)
        for syn in request.form.getlist('synonyms[]'):
            add_unique_relation(word.id, WordSynonym, syn)

        # Antonimlar - YANGI
        for ant in request.form.getlist('antonyms[]'):
            add_unique_relation(word.id, WordAntonym, ant)

        # Giperonimlar - YANGI
        for hyp in request.form.getlist('hyperonyms[]'):
            add_unique_relation(word.id, WordHyperonym, hyp)

        # Giponimlar - YANGI
        for hypo in request.form.getlist('hyponyms[]'):
            add_unique_relation(word.id, WordHyponym, hypo)

        # Xolonimlar - YANGI
        for hol in request.form.getlist('holonyms[]'):
            add_unique_relation(word.id, WordHolonym, hol)

        # Meronimlar - YANGI
        for mer in request.form.getlist('meronyms[]'):
            add_unique_relation(word.id, WordMeronym, mer)

        # Omonimlar - YANGI
        for hom in request.form.getlist('homonyms[]'):
            add_unique_relation(word.id, WordHomonym, hom)

        # Paronimlar - YANGI
        for par in request.form.getlist('paronyms[]'):
            add_unique_relation(word.id, WordParonym, par)

        # Qo'llanish sohalari - YANGI
        for area in request.form.getlist('usage_areas[]'):
            add_unique_relation(word.id, WordUsageArea, area, 'area')

        db.session.commit()
        flash(f'So\'z "{word_text}" muvaffaqiyatli qo\'shildi', 'success')
        return redirect(url_for('admin.words'))

    return render_template('admin/word_form.html')


@admin_bp.route('/words/edit/<int:word_id>', methods=['GET', 'POST'])
@admin_required
def edit_word(word_id):
    word = Word.query.get_or_404(word_id)

    if request.method == 'POST':
        word.word = request.form.get('word', '').strip().lower()
        word.definition = request.form.get('definition', '')
        word.etymology = request.form.get('etymology', '')
        word.translation_en = request.form.get('translation_en', '')

        # Eski bog'lanishlarni o'chirish
        WordCategory.query.filter_by(word_id=word.id).delete()
        WordSynonym.query.filter_by(word_id=word.id).delete()
        WordAntonym.query.filter_by(word_id=word.id).delete()
        WordHyperonym.query.filter_by(word_id=word.id).delete()
        WordHyponym.query.filter_by(word_id=word.id).delete()
        WordHolonym.query.filter_by(word_id=word.id).delete()
        WordMeronym.query.filter_by(word_id=word.id).delete()
        WordHomonym.query.filter_by(word_id=word.id).delete()
        WordParonym.query.filter_by(word_id=word.id).delete()
        WordUsageArea.query.filter_by(word_id=word.id).delete()

        # Yangi bog'lanishlar qo'shish (без дубликатов)

        # Kategoriyalar
        add_unique_categories(word.id, request.form.getlist('categories[]'))

        # Sinonimlar
        for syn in request.form.getlist('synonyms[]'):
            add_unique_relation(word.id, WordSynonym, syn)

        # Antonimlar
        for ant in request.form.getlist('antonyms[]'):
            add_unique_relation(word.id, WordAntonym, ant)

        # Giperonimlar
        for hyp in request.form.getlist('hyperonyms[]'):
            add_unique_relation(word.id, WordHyperonym, hyp)

        # Giponimlar
        for hypo in request.form.getlist('hyponyms[]'):
            add_unique_relation(word.id, WordHyponym, hypo)

        # Xolonimlar
        for hol in request.form.getlist('holonyms[]'):
            add_unique_relation(word.id, WordHolonym, hol)

        # Meronimlar
        for mer in request.form.getlist('meronyms[]'):
            add_unique_relation(word.id, WordMeronym, mer)

        # Omonimlar
        for hom in request.form.getlist('homonyms[]'):
            add_unique_relation(word.id, WordHomonym, hom)

        # Paronimlar
        for par in request.form.getlist('paronyms[]'):
            add_unique_relation(word.id, WordParonym, par)

        # Qo'llanish sohalari
        for area in request.form.getlist('usage_areas[]'):
            add_unique_relation(word.id, WordUsageArea, area, 'area')

        db.session.commit()
        flash(f'So\'z "{word.word}" muvaffaqiyatli yangilandi', 'success')
        return redirect(url_for('admin.words'))

    # Forma uchun ma'lumotlar
    word_data = {
        'id': word.id,
        'word': word.word,
        'definition': word.definition,
        'etymology': word.etymology,
        'translation_en': word.translation_en,
        'categories': [cat.category for cat in word.categories],
        'synonyms': [syn.related_word for syn in word.synonyms],
        'antonyms': [ant.related_word for ant in word.antonyms],
        'hyperonyms': [hyp.related_word for hyp in word.hyperonyms],
        'hyponyms': [hypo.related_word for hypo in word.hyponyms],
        'holonyms': [hol.related_word for hol in word.holonyms],
        'meronyms': [mer.related_word for mer in word.meronyms],
        'homonyms': [hom.related_word for hom in word.homonyms],
        'paronyms': [par.related_word for par in word.paronyms],
        'usage_areas': [area.area for area in word.usage_areas]
    }

    return render_template('admin/word_form.html', word=word_data)


@admin_bp.route('/words/delete/<int:word_id>')
@admin_required
def delete_word(word_id):
    word = Word.query.get_or_404(word_id)
    word_text = word.word
    db.session.delete(word)
    db.session.commit()
    flash(f'So\'z "{word_text}" o\'chirildi', 'success')
    return redirect(url_for('admin.words'))


@admin_bp.route('/categories')
@admin_required
def categories():
    """Kategoriyalarni boshqarish sahifasi"""
    categories = db.session.query(WordCategory.category).distinct().order_by(WordCategory.category).all()
    categories = [cat[0] for cat in categories]

    category_words_count = {}
    categories_with_words = 0

    for category in categories:
        count = WordCategory.query.filter_by(category=category).count()
        category_words_count[category] = count
        if count > 0:
            categories_with_words += 1

    return render_template('admin/categories.html',
                           categories=categories,
                           category_words_count=category_words_count,
                           categories_with_words=categories_with_words)


@admin_bp.route('/categories/add', methods=['POST'])
@admin_required
def add_category():
    """Yangi kategoriya qo'shish"""
    category_name = request.form.get('category_name', '').strip().lower()

    if not category_name:
        flash('Kategoriya nomi kiritilishi shart', 'danger')
        return redirect(url_for('admin.categories'))

    existing = db.session.query(WordCategory).filter_by(category=category_name).first()
    if existing:
        flash(f'"{category_name}" kategoriyasi allaqachon mavjud', 'danger')
        return redirect(url_for('admin.categories'))

    # Vaqtinchalik xizmat so'zi yaratish
    test_word = Word(
        word=f"_category_placeholder_{category_name}",
        definition="Xizmat ko'rsatish uchun yozuv"
    )
    db.session.add(test_word)
    db.session.flush()

    word_cat = WordCategory(word_id=test_word.id, category=category_name)
    db.session.add(word_cat)
    db.session.commit()

    flash(f'"{category_name}" kategoriyasi muvaffaqiyatli qo\'shildi', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/edit/<path:category>', methods=['GET', 'POST'])
@admin_required
def edit_category(category):
    """Kategoriyani tahrirlash"""
    if request.method == 'POST':
        new_name = request.form.get('category_name', '').strip().lower()

        if not new_name:
            flash('Kategoriya nomi kiritilishi shart', 'danger')
            return redirect(url_for('admin.categories'))

        if category == new_name:
            flash('Kategoriya nomi o\'zgarmadi', 'info')
            return redirect(url_for('admin.categories'))

        existing = WordCategory.query.filter_by(category=new_name).first()
        if existing:
            flash(f'"{new_name}" kategoriyasi allaqachon mavjud', 'danger')
            return redirect(url_for('admin.categories'))

        categories = WordCategory.query.filter_by(category=category).all()
        if categories:
            for cat in categories:
                cat.category = new_name
            db.session.commit()
            flash(f'"{category}" -> "{new_name}" muvaffaqiyatli yangilandi', 'success')
        else:
            flash(f'"{category}" kategoriyasi topilmadi', 'danger')

        return redirect(url_for('admin.categories'))

    return render_template('admin/edit_category.html', category=category)


@admin_bp.route('/categories/delete/<path:category>')
@admin_required
def delete_category(category):
    """Kategoriyani o'chirish"""
    words_with_category = WordCategory.query.filter_by(category=category).all()

    if words_with_category:
        real_words = []
        placeholder_ids = []

        for cat in words_with_category:
            word = Word.query.get(cat.word_id)
            if word:
                if word.word.startswith('_category_placeholder_'):
                    placeholder_ids.append(cat.id)
                else:
                    real_words.append(word.word)

        if real_words:
            flash(
                f'"{category}" kategoriyasida so\'zlar bor: {", ".join(real_words[:3])}. Avval ularni o\'chiring yoki boshqa kategoriyaga o\'tkazing.',
                'danger')
        elif placeholder_ids:
            WordCategory.query.filter(WordCategory.id.in_(placeholder_ids)).delete(synchronize_session=False)
            Word.query.filter(Word.word.like('_category_placeholder_%')).delete(synchronize_session=False)
            db.session.commit()
            flash(f'"{category}" kategoriyasi o\'chirildi', 'success')
    else:
        flash(f'"{category}" kategoriyasi topilmadi', 'danger')

    return redirect(url_for('admin.categories'))


@admin_bp.route('/import-export')
@admin_required
def import_export():
    """Import/Export sahifasi"""
    return render_template('admin/import_export.html')


@admin_bp.route('/api/export-json')
@admin_required
def export_json():
    """Butun ma'lumotlar bazasini JSON formatda eksport qilish"""
    words = Word.query.all()
    data = []

    for word in words:
        # Placeholder so'zlarni o'tkazib yuborish
        if word.word.startswith('_category_placeholder_'):
            continue

        word_data = {
            'word': word.word,
            'definition': word.definition,
            'etymology': word.etymology,
            'translation_en': word.translation_en,
            'categories': [cat.category for cat in word.categories],
            'synonyms': [syn.related_word for syn in word.synonyms],
            'antonyms': [ant.related_word for ant in word.antonyms],
            'hyperonyms': [hyp.related_word for hyp in word.hyperonyms],
            'hyponyms': [hypo.related_word for hypo in word.hyponyms],
            'holonyms': [hol.related_word for hol in word.holonyms],
            'meronyms': [mer.related_word for mer in word.meronyms],
            'homonyms': [hom.related_word for hom in word.homonyms],
            'paronyms': [par.related_word for par in word.paronyms if
                         par.related_word and par.related_word.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '']],
            'usage_areas': [area.area for area in word.usage_areas]
        }
        data.append(word_data)

    response = jsonify(data)
    response.headers['Content-Disposition'] = 'attachment; filename=thesaurus_export.json'
    response.headers['Content-Type'] = 'application/json'
    return response


@admin_bp.route('/api/import-json', methods=['POST'])
@admin_required
def import_json():
    """JSON fayldan ma'lumotlarni import qilish (dublikatlar bilan birga)"""
    import json

    if 'file' not in request.files:
        flash('Fayl tanlanmagan', 'danger')
        return redirect(url_for('admin.import_export'))

    file = request.files['file']
    if file.filename == '':
        flash('Fayl tanlanmagan', 'danger')
        return redirect(url_for('admin.import_export'))

    if not file.filename.endswith('.json'):
        flash('Faqat JSON fayllar qabul qilinadi', 'danger')
        return redirect(url_for('admin.import_export'))

    try:
        content = file.read().decode('utf-8')
        data = json.loads(content)

        clear_existing = request.form.get('clear_existing') == 'on'

        if clear_existing:
            # Placeholder so'zlarni saqlab qolish
            Word.query.filter(Word.word.notlike('_category_placeholder_%')).delete()
            db.session.commit()
            flash('Mavjud ma\'lumotlar tozalandi', 'info')

        imported_count = 0
        duplicate_in_json = 0
        errors = []

        # Dublikatlarni aniqlash uchun vaqtinchalik set
        temp_words = []

        for idx, item in enumerate(data):
            # So'z nomini topish
            word_text = None
            for key in ['word', 'Qishloq xo\'jaligi terminlari', 'Qishloq xo\'jaligi  terminlari', 'soz', 'name']:
                if key in item and item[key]:
                    word_text = str(item[key]).strip().lower()
                    break

            if not word_text:
                continue

            # Dublikatlarni sanash uchun
            if word_text in temp_words:
                duplicate_in_json += 1
            temp_words.append(word_text)

            try:
                # Ta'rif (Izohi)
                definition = item.get('Izohi', '')
                if isinstance(definition, list):
                    definition = ' '.join(definition)
                elif not definition:
                    definition = item.get('определение', '')
                if not definition:
                    definition = item.get('definition', '')
                if not definition:
                    definition = "Ta'rif mavjud emas"

                # Etimologiya
                etymology = item.get('Etimologiyasi', '')
                if isinstance(etymology, list):
                    etymology = ' '.join(etymology)

                # Ingliz tiliga tarjima
                translation_en = item.get('Tarjimasi (ingliz tili)', '')
                if not translation_en:
                    translation_en = item.get('translation_en', '')
                if translation_en and isinstance(translation_en, str):
                    translation_en = translation_en.strip()

                # YANGI SO'Z YARATAMIZ (dublikat bo'lsa ham)
                word = Word(
                    word=word_text,
                    definition=definition,
                    etymology=etymology,
                    translation_en=translation_en
                )
                db.session.add(word)
                db.session.flush()

                # Kategoriya (turkumi) - с защитой от дубликатов
                turkum = item.get('turkumi', '')
                if turkum:
                    added_cats = set()
                    for cat in str(turkum).split(','):
                        cat = cat.strip()
                        if cat and cat not in added_cats:
                            added_cats.add(cat)
                            existing_cat = WordCategory.query.filter_by(word_id=word.id, category=cat).first()
                            if not existing_cat:
                                db.session.add(WordCategory(word_id=word.id, category=cat))

                # Sinonimlar - с защитой от дубликатов
                sinonim = item.get('sinonimi (ma\'nodoshi)', '')
                if not sinonim:
                    sinonim = item.get('sinonimi', '')
                if sinonim:
                    added_syns = set()
                    for syn in str(sinonim).split(','):
                        syn = syn.strip()
                        if syn and syn.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '', '-', '—']:
                            if syn not in added_syns:
                                added_syns.add(syn)
                                existing_syn = WordSynonym.query.filter_by(word_id=word.id, related_word=syn).first()
                                if not existing_syn:
                                    db.session.add(WordSynonym(word_id=word.id, related_word=syn))

                # Antonimlar - с защитой от дубликатов
                antonim = item.get('antonimi (zid ma\'nosi)', '')
                if not antonim:
                    antonim = item.get('antonimi', '')
                if antonim:
                    added_ants = set()
                    for ant in str(antonim).split(','):
                        ant = ant.strip()
                        if ant and ant.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '', '-', '—']:
                            if ant not in added_ants:
                                added_ants.add(ant)
                                existing_ant = WordAntonym.query.filter_by(word_id=word.id, related_word=ant).first()
                                if not existing_ant:
                                    db.session.add(WordAntonym(word_id=word.id, related_word=ant))

                # Giperonimlar - с защитой от дубликатов
                giperonim = item.get('giperonimi (jins)', '')
                if not giperonim:
                    giperonim = item.get('giperonimi', '')
                if giperonim:
                    added_hyps = set()
                    for hyp in str(giperonim).split(','):
                        hyp = hyp.strip()
                        if hyp and hyp.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '']:
                            if hyp not in added_hyps:
                                added_hyps.add(hyp)
                                existing_hyp = WordHyperonym.query.filter_by(word_id=word.id, related_word=hyp).first()
                                if not existing_hyp:
                                    db.session.add(WordHyperonym(word_id=word.id, related_word=hyp))

                # Giponimlar - с защитой от дубликатов
                giponim = item.get('giponimi (tur)', '')
                if not giponim:
                    giponim = item.get('giponimi', '')
                if giponim:
                    added_hypos = set()
                    for hypo in str(giponim).split(','):
                        hypo = hypo.strip()
                        if hypo and hypo.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '']:
                            if hypo not in added_hypos:
                                added_hypos.add(hypo)
                                existing_hypo = WordHyponym.query.filter_by(word_id=word.id, related_word=hypo).first()
                                if not existing_hypo:
                                    db.session.add(WordHyponym(word_id=word.id, related_word=hypo))

                # Xolonimlar - с защитой от дубликатов
                xolonim = item.get('xolonim (butun)i', '')
                if not xolonim:
                    xolonim = item.get('xolonim', '')
                if xolonim:
                    added_hols = set()
                    for hol in str(xolonim).split(','):
                        hol = hol.strip()
                        if hol and hol.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '']:
                            if hol not in added_hols:
                                added_hols.add(hol)
                                existing_hol = WordHolonym.query.filter_by(word_id=word.id, related_word=hol).first()
                                if not existing_hol:
                                    db.session.add(WordHolonym(word_id=word.id, related_word=hol))

                # Meronimlar - с защитой от дубликатов
                meronim = item.get('meronimi (qismi)', '')
                if not meronim:
                    meronim = item.get('meronim', '')
                if meronim:
                    added_mers = set()
                    for mer in str(meronim).split(','):
                        mer = mer.strip()
                        if mer and mer.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '']:
                            if mer not in added_mers:
                                added_mers.add(mer)
                                existing_mer = WordMeronym.query.filter_by(word_id=word.id, related_word=mer).first()
                                if not existing_mer:
                                    db.session.add(WordMeronym(word_id=word.id, related_word=mer))

                # Omonimlar - с защитой от дубликатов
                omonim = item.get('omonimi (shakldoshi)', '')
                if not omonim:
                    omonim = item.get('omonim', '')
                if omonim and omonim not in [None, 'null', 'None', '']:
                    added_homs = set()
                    for hom in str(omonim).split(','):
                        hom = hom.strip()
                        if hom and hom.lower() not in ['yo\'q', 'yoq', 'нет', 'none', 'null', '']:
                            if hom not in added_homs:
                                added_homs.add(hom)
                                existing_hom = WordHomonym.query.filter_by(word_id=word.id, related_word=hom).first()
                                if not existing_hom:
                                    db.session.add(WordHomonym(word_id=word.id, related_word=hom))

                # Paronimlar - с защитой от дубликатов
                paronim = item.get('paronimi (talaffuzdoshi)', '')
                if not paronim:
                    paronim = item.get('paronim', '')
                if paronim and paronim not in [None, 'null', 'None', '']:
                    added_pars = set()
                    for par in str(paronim).split(','):
                        par = par.strip()
                        if par and par.lower() not in ['yo\'q', 'yoq', 'нет', 'none', 'null', '']:
                            if par not in added_pars:
                                added_pars.add(par)
                                existing_par = WordParonym.query.filter_by(word_id=word.id, related_word=par).first()
                                if not existing_par:
                                    db.session.add(WordParonym(word_id=word.id, related_word=par))

                # Qo'llanilish sohalari - с защитой от дубликатов
                usage = ''
                usage_keys = ['qaysi sohada qo\'llanilishi', 'qaysi sohada qollanilishi',
                              'qollanilishi', 'usage_areas', 'qollanilish_sohasi', 'qaysi sohada qo‘llanilishi']

                for key in usage_keys:
                    if key in item and item[key]:
                        usage = item[key]
                        break

                if usage and str(usage).strip():
                    added_areas = set()
                    for area in str(usage).split(','):
                        area = area.strip()
                        if area and area.lower() not in ['yo\'q', 'yoq', 'нет', 'none', '', '-', '—', 'null']:
                            if area not in added_areas:
                                added_areas.add(area)
                                existing_area = WordUsageArea.query.filter_by(word_id=word.id, area=area).first()
                                if not existing_area:
                                    db.session.add(WordUsageArea(word_id=word.id, area=area))

                imported_count += 1

                # Har 100 ta so'zda commit qilish (tezlik uchun)
                if imported_count % 100 == 0:
                    db.session.commit()
                    print(f"✅ {imported_count} ta so'z import qilindi...")

            except Exception as e:
                errors.append(f"'{word_text}': {str(e)}")
                print(f"❌ ERROR for '{word_text}': {str(e)}")
                continue

        db.session.commit()

        # Jami natijalar
        total_records = Word.query.filter(Word.word.notlike('_category_placeholder_%')).count()
        unique_words = db.session.query(Word.word).distinct().filter(
            Word.word.notlike('_category_placeholder_%')).count()
        total_usage = WordUsageArea.query.count()

        msg = f'✅ Jami: {len(data)} ta yozuv (JSON da)\n'
        msg += f'✅ Import qilindi: {imported_count} ta yozuv\n'
        msg += f'⚠️ JSON da dublikatlar: {duplicate_in_json} ta\n'
        msg += f'📊 Jami yozuvlar bazada: {total_records} ta\n'
        msg += f'🔍 Unikal so\'zlar: {unique_words} ta\n'
        msg += f'🏷️ Qo\'llanilish sohalari: {total_usage} ta yozuv'

        if errors:
            msg += f'\n❌ Xatolar: {len(errors)} ta'

        flash(msg, 'success')

    except json.JSONDecodeError as e:
        flash(f'JSON fayl xatosi: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Import xatosi: {str(e)}', 'danger')
        print(f"❌ Import exception: {str(e)}")

    return redirect(url_for('admin.import_export'))


@admin_bp.route('/api/words/search')
def api_words_search():
    """API so'zlarni qidirish uchun"""
    query = request.args.get('q', '').lower()
    if len(query) < 2:
        return jsonify([])

    words = Word.query.filter(
        Word.word.like(f'%{query}%'),
        ~Word.word.startswith('_category_placeholder_')  # Placeholderlarni o'tkazib yuborish
    ).limit(10).all()

    return jsonify([word.word for word in words])


def create_admin():
    """Administrator yaratish (birinchi ishga tushirishda)"""
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print('✅ Admin created: username=admin, password=admin123')
    else:
        print('✅ Admin already exists')


@admin_bp.route('/categories/edit-ajax', methods=['POST'])
@admin_required
def edit_category_ajax():
    """Редактирование категории через AJAX (для модального окна)"""
    old_name = request.form.get('old_name', '').strip().lower()
    new_name = request.form.get('category_name', '').strip().lower()

    if not new_name:
        flash('Kategoriya nomi kiritilishi shart', 'danger')
        return redirect(url_for('admin.categories'))

    if old_name == new_name:
        flash('Kategoriya nomi o\'zgarmadi', 'info')
        return redirect(url_for('admin.categories'))

    # Проверяем, существует ли уже категория с новым именем
    existing = WordCategory.query.filter_by(category=new_name).first()
    if existing and old_name != new_name:
        flash(f'"{new_name}" kategoriyasi allaqachon mavjud', 'danger')
        return redirect(url_for('admin.categories'))

    # Обновляем все записи с этой категорией
    categories = WordCategory.query.filter_by(category=old_name).all()
    if categories:
        for cat in categories:
            cat.category = new_name
        db.session.commit()
        flash(f'"{old_name}" -> "{new_name}" muvaffaqiyatli yangilandi', 'success')
    else:
        flash(f'"{old_name}" kategoriyasi topilmadi', 'danger')

    return redirect(url_for('admin.categories'))