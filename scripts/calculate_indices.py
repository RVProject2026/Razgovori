#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Скрипт расчёта индексов ИЦЛП, ИКАН и ИЦВ для образовательных текстов
=============================================================================
Автор: Шаповалов М.И.
Назначение: Анализ текста на основе онтологии и расчёт трёх ключевых метрик.
Использование: python scripts/calculate_indices.py
=============================================================================
"""

import json
import re
from pathlib import Path
from collections import defaultdict
import context_filter

def load_ontology(file_path):
    """Загрузка онтологии из JSON."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_words(text):
    """Извлечение всех слов из текста для подсчёта общего объёма."""
    return re.findall(r'\b[а-яА-ЯёЁa-zA-Z]+\b', text)

def count_markers(text, ontology):
    """Подсчёт маркеров и их валентности в тексте."""
    text_lower = text.lower()
    stats = {
        'universal': {'count': 0, 'valence_sum': 0.0, 'found': set()},
        'ideological': {'count': 0, 'valence_sum': 0.0, 'found': set()},
        'social': {'count': 0, 'valence_sum': 0.0, 'found': set()}
    }
    total_markers_found = 0
    
    for cluster in ontology['clusters']:
        ctype = cluster['type']
        for subcat in cluster['subcategories']:
            default_valence = subcat.get('default_valence', 1.0)
            default_weight = subcat.get('default_weight', 1.0)
            
            for item in subcat['lexemes']:
                # Поддержка как строк, так и словарей с valence/weight
                if isinstance(item, str):
                    lexeme = item.lower()
                    valence = default_valence
                    weight = default_weight
                else:
                    lexeme = item['word'].lower()
                    valence = item.get('valence', default_valence)
                    weight = item.get('weight', default_weight)
                
                # Поиск маркера в тексте (учитываем фразы типа "малая родина")
                if lexeme in text_lower:
                    # Для коротких слов (<=3 букв) проверяем границы слова, чтобы избежать ложных срабатываний
                    if len(lexeme) <= 3:
                        pattern = r'\b' + re.escape(lexeme) + r'\b'
                        if not re.search(pattern, text_lower):
                            continue
                    
                    stats[ctype]['count'] += 1
                    stats[ctype]['valence_sum'] += (valence * weight)
                    stats[ctype]['found'].add(lexeme)
                    total_markers_found += 1
                    
    return stats, total_markers_found

def calculate_indices(text, ontology):
    """Расчёт итоговых метрик."""
    words = extract_words(text)
    total_words = len(words)
    
    stats, total_markers = count_markers(text, ontology)
    
    # 1. ИЦЛП: маркеров на 1000 слов
    iclp = (total_markers / total_words * 1000) if total_words > 0 else 0
    
    # 2. ИКАН: универсальные / (универсальные + идеологические + социальные)
    uni = stats['universal']['count']
    ideo = stats['ideological']['count']
    soc = stats['social']['count']
    total_valued = uni + ideo + soc
    
    ican = (uni / total_valued) if total_valued > 0 else 0
    
    # 3. ИЦВ: средняя валентность найденных маркеров (нормированная от 0.0 до 1.0)
    total_valence = stats['universal']['valence_sum'] + stats['ideological']['valence_sum'] + stats['social']['valence_sum']
    avg_valence = (total_valence / total_markers) if total_markers > 0 else 0
    icv = (avg_valence + 1.0) / 2.0  # Перевод шкалы из [-1, 1] в [0, 1]
    
    return {
        'total_words': total_words,
        'total_markers': total_markers,
        'iclp': round(iclp, 2),
        'ican': round(ican, 2),
        'icv': round(icv, 2),
        'stats': stats
    }

def main():
    ontology_path = Path("data/ontology.json")
    text_path = Path("examples/sample_teacher_reflection.txt")
    
    if not ontology_path.exists():
        print("❌ Не найден файл онтологии: data/ontology.json")
        return
    if not text_path.exists():
        print("❌ Не найден файл текста: examples/sample_teacher_reflection.txt")
        return
        
    print("🔄 Загрузка онтологии и текста...")
    ontology = load_ontology(ontology_path)
    with open(text_path, 'r', encoding='utf-8') as f:
        text = f.read()
        
    print("🔄 Анализ текста и расчёт индексов...\n")
    results = calculate_indices(text, ontology)
    
    print("=" * 75)
    print("📊 РЕЗУЛЬТАТЫ АНАЛИЗА ЦЕННОСТНО-СМЫСЛОВОЙ СОГЛАСОВАННОСТИ")
    print("=" * 75)
    print(f"📄 Файл: {text_path.name}")
    print(f"📝 Объём текста: {results['total_words']} слов")
    print(f"🎯 Найдено ценностных маркеров: {results['total_markers']}")
    print("-" * 75)
    
    # Интерпретация ИЦЛП
    iclp_interp = "Высокая" if results['iclp'] > 70 else "Средняя" if results['iclp'] > 40 else "Низкая"
    print(f"📈 ИЦЛП (Ценностно-лексическая плотность): {results['iclp']}")
    print(f"   → Интерпретация: {iclp_interp} насыщенность ценностной лексикой")
    
    # Интерпретация ИКАН
    ican_interp = "Высокая адаптивность (гуманистический уклон)" if results['ican'] > 0.7 else "Смешанный тип" if results['ican'] > 0.4 else "Высокая идеологизация"
    print(f"📈 ИКАН (Культурно-адаптивная нейтральность): {results['ican']}")
    print(f"   → Интерпретация: {ican_interp}")
    
    # Интерпретация ИЦВ
    icv_interp = "Ярко выраженный созидательный заряд" if results['icv'] > 0.85 else "Нейтрально-позитивный" if results['icv'] > 0.65 else "Нейтральный/Спорный"
    print(f"📈 ИЦВ (Ценностная валентность): {results['icv']}")
    print(f"   → Интерпретация: {icv_interp}")
    
    print("-" * 75)
    print("📋 Распределение маркеров по кластерам:")
    print(f"   • Универсально-культурный: {results['stats']['universal']['count']} маркеров")
    print(f"   • Конъюнктурно-политический: {results['stats']['ideological']['count']} маркеров")
    print(f"   • Социально-активный: {results['stats']['social']['count']} маркеров")
    print("=" * 75)
    print("✅ Анализ завершён успешно. Данные готовы для включения в статью ВАК.")

if __name__ == "__main__":
    main()
