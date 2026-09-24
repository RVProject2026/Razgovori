#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Скрипт валидации онтологии традиционных ценностей
=============================================================================
Автор: Шаповалов М.И.
Назначение: Проверка целостности структуры, отсутствие дубликатов, 
            корректность значений valence и weight
Использование: python scripts/validate_ontology.py [путь_к_файлу]
По умолчанию: data/ontology.json

Скрипт используется:
  - Локально для ручной проверки
  - Автоматически через GitHub Actions при каждом изменении онтологии
  - Для подготовки отчёта в статью ВАК (раздел "Валидация данных")
=============================================================================
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any


# =============================================================================
# КОНСТАНТЫ
# =============================================================================
VALID_CLUSTER_TYPES = {"universal", "ideological", "social"}
VALID_VALENCE_RANGE = (-1.0, 1.0)
VALID_WEIGHT_RANGE = (0.0, 1.0)

# Символы для вывода
OK = "✅"
WARN = "⚠️"
ERR = "❌"
INFO = "ℹ️"


# =============================================================================
# ФУНКЦИИ ВАЛИДАЦИИ
# =============================================================================

def load_ontology(file_path: Path) -> Tuple[bool, Any]:
    """Загрузка и базовая проверка JSON-файла."""
    print(f"\n{INFO} Загрузка файла: {file_path}")
    print("=" * 70)
    
    if not file_path.exists():
        print(f"{ERR} Файл не найден: {file_path}")
        return False, None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"{OK} Файл успешно загружен (формат JSON валиден)")
        return True, data
    except json.JSONDecodeError as e:
        print(f"{ERR} Ошибка парсинга JSON: {e}")
        return False, None
    except UnicodeDecodeError as e:
        print(f"{ERR} Ошибка кодировки UTF-8: {e}")
        return False, None


def validate_metadata(data: Dict) -> bool:
    """Проверка наличия и корректности метаданных."""
    print(f"\n{INFO} Проверка метаданных (metadata)...")
    
    required_fields = ["version", "created", "author", "total_lexemes", "sources"]
    missing = [f for f in required_fields if f not in data.get("metadata", {})]
    
    if missing:
        print(f"{ERR} Отсутствуют обязательные поля: {missing}")
        return False
    
    metadata = data["metadata"]
    print(f"{OK} Версия онтологии: {metadata['version']}")
    print(f"{OK} Автор: {metadata['author']}")
    print(f"{OK} Дата создания: {metadata['created']}")
    print(f"{OK} Источников: {len(metadata['sources'])}")
    
    # Проверка заявленного количества лексем
    declared_total = metadata.get("total_lexemes", 0)
    print(f"{INFO} Заявлено лексем в metadata: {declared_total}")
    
    return True


def validate_structure(data: Dict) -> Tuple[bool, List[str]]:
    """Проверка структуры кластеров и подкатегорий."""
    print(f"\n{INFO} Проверка структуры данных...")
    errors = []
    
    if "clusters" not in data:
        print(f"{ERR} Отсутствует ключ 'clusters'")
        return False, ["Нет clusters"]
    
    clusters = data["clusters"]
    print(f"{OK} Найдено кластеров: {len(clusters)}")
    
    for i, cluster in enumerate(clusters):
        cluster_name = cluster.get("name", f"Кластер #{i+1}")
        
        # Проверка обязательных полей кластера
        required_cluster_fields = ["id", "name", "type", "subcategories"]
        missing = [f for f in required_cluster_fields if f not in cluster]
        if missing:
            errors.append(f"Кластер '{cluster_name}': отсутствуют поля {missing}")
            continue
        
        # Проверка type
        if cluster["type"] not in VALID_CLUSTER_TYPES:
            errors.append(
                f"Кластер '{cluster_name}': недопустимый type='{cluster['type']}'. "
                f"Допустимы: {VALID_CLUSTER_TYPES}"
            )
        
        # Проверка подкатегорий
        subcats = cluster.get("subcategories", [])
        if not subcats:
            errors.append(f"Кластер '{cluster_name}': нет подкатегорий")
            continue
        
        print(f"{OK} Кластер '{cluster_name}' (type={cluster['type']}): "
              f"{len(subcats)} подкатегорий")
        
        for j, subcat in enumerate(subcats):
            subcat_name = subcat.get("name", f"Подкатегория #{j+1}")
            
            required_subcat_fields = ["name", "lexemes"]
            missing = [f for f in required_subcat_fields if f not in subcat]
            if missing:
                errors.append(
                    f"Кластер '{cluster_name}' / '{subcat_name}': "
                    f"отсутствуют поля {missing}"
                )
                continue
            
            # Проверка valence и weight (если указаны)
            if "default_valence" in subcat:
                v = subcat["default_valence"]
                if not (VALID_VALENCE_RANGE[0] <= v <= VALID_VALENCE_RANGE[1]):
                    errors.append(
                        f"'{cluster_name}' / '{subcat_name}': "
                        f"default_valence={v} вне диапазона {VALID_VALENCE_RANGE}"
                    )
            
            if "default_weight" in subcat:
                w = subcat["default_weight"]
                if not (VALID_WEIGHT_RANGE[0] <= w <= VALID_WEIGHT_RANGE[1]):
                    errors.append(
                        f"'{cluster_name}' / '{subcat_name}': "
                        f"default_weight={w} вне диапазона {VALID_WEIGHT_RANGE}"
                    )
    
    if errors:
        for err in errors:
            print(f"{ERR} {err}")
        return False, errors
    
    print(f"{OK} Структура данных полностью корректна")
    return True, []


def find_duplicates(data: Dict) -> Dict[str, List[str]]:
    """
    Поиск дубликатов на трёх уровнях:
      1. Внутри каждой подкатегории
      2. Внутри каждого кластера (между подкатегориями)
      3. Глобально (между всеми кластерами)
    """
    print(f"\n{INFO} Поиск дубликатов лексем...")
    
    duplicates = {
        "within_subcategory": [],
        "within_cluster": [],
        "global": []
    }
    
    all_lexemes_global = []
    
    for cluster in data["clusters"]:
        cluster_name = cluster.get("name", "Без названия")
        cluster_lexemes = []
        
        for subcat in cluster.get("subcategories", []):
            subcat_name = subcat.get("name", "Без названия")
            lexemes = subcat.get("lexemes", [])
            
            # Нормализация для корректного сравнения
            normalized = [lex.strip().lower() for lex in lexemes if isinstance(lex, str)]
            
            # 1. Проверка внутри подкатегории
            counter = Counter(normalized)
            dups = [lex for lex, count in counter.items() if count > 1]
            if dups:
                duplicates["within_subcategory"].extend([
                    f"'{cluster_name}' / '{subcat_name}': {dups}"
                ])
            
            cluster_lexemes.extend(normalized)
            all_lexemes_global.extend([(lex, cluster_name, subcat_name) 
                                       for lex in normalized])
        
        # 2. Проверка внутри кластера
        counter = Counter(cluster_lexemes)
        dups = [lex for lex, count in counter.items() if count > 1]
        if dups:
            duplicates["within_cluster"].append(
                f"'{cluster_name}': {dups}"
            )
    
    # 3. Глобальная проверка
    global_counter = Counter([item[0] for item in all_lexemes_global])
    global_dups = [lex for lex, count in global_counter.items() if count > 1]
    
    if global_dups:
        # Показываем, в каких кластерах встречается дубликат
        for dup in global_dups:
            locations = [f"{cl}/{sc}" for lex, cl, sc in all_lexemes_global 
                        if lex == dup]
            duplicates["global"].append(f"'{dup}': встречается в {locations}")
    
    # Вывод результатов
    if duplicates["within_subcategory"]:
        print(f"{WARN} Дубликаты внутри подкатегорий: "
              f"{len(duplicates['within_subcategory'])}")
        for item in duplicates["within_subcategory"][:5]:
            print(f"   {WARN} {item}")
    else:
        print(f"{OK} Дубликатов внутри подкатегорий не обнаружено")
    
    if duplicates["within_cluster"]:
        print(f"{WARN} Дубликаты внутри кластеров: "
              f"{len(duplicates['within_cluster'])}")
        for item in duplicates["within_cluster"][:5]:
            print(f"   {WARN} {item}")
    else:
        print(f"{OK} Дубликатов внутри кластеров не обнаружено")
    
    if duplicates["global"]:
        print(f"{WARN} Глобальные дубликаты (между кластерами): "
              f"{len(duplicates['global'])}")
        for item in duplicates["global"][:10]:
            print(f"   {WARN} {item}")
        print(f"{INFO} Примечание: глобальные дубликаты допустимы, если лексема "
              f"осмысленно относится к нескольким кластерам (например, 'Кремль')")
    else:
        print(f"{OK} Глобальных дубликатов не обнаружено")
    
    return duplicates


def calculate_statistics(data: Dict) -> Dict[str, Any]:
    """Подсчёт итоговой статистики по онтологии."""
    stats = {
        "total_clusters": 0,
        "total_subcategories": 0,
        "total_lexemes_raw": 0,
        "total_lexemes_unique": 0,
        "by_cluster": {},
        "by_type": defaultdict(int)
    }
    
    all_lexemes = set()
    
    for cluster in data["clusters"]:
        cluster_name = cluster.get("name", "Без названия")
        cluster_type = cluster.get("type", "unknown")
        cluster_count = 0
        
        for subcat in cluster.get("subcategories", []):
            lexemes = subcat.get("lexemes", [])
            cluster_count += len(lexemes)
            stats["total_subcategories"] += 1
            all_lexemes.update(lex.strip().lower() for lex in lexemes 
                              if isinstance(lex, str))
        
        stats["total_clusters"] += 1
        stats["total_lexemes_raw"] += cluster_count
        stats["by_cluster"][cluster_name] = cluster_count
        stats["by_type"][cluster_type] += cluster_count
    
    stats["total_lexemes_unique"] = len(all_lexemes)
    
    return stats


def print_statistics(stats: Dict[str, Any]):
    """Красивый вывод статистики."""
    print(f"\n{'=' * 70}")
    print(f"📊 ИТОГОВАЯ СТАТИСТИКА ОНТОЛОГИИ")
    print(f"{'=' * 70}")
    print(f"  Кластеров:              {stats['total_clusters']}")
    print(f"  Подкатегорий:           {stats['total_subcategories']}")
    print(f"  Лексем (с повторами):   {stats['total_lexemes_raw']}")
    print(f"  Лексем (уникальных):    {stats['total_lexemes_unique']}")
    print(f"{'─' * 70}")
    print(f"  Распределение по кластерам:")
    for name, count in stats["by_cluster"].items():
        print(f"    • {name}: {count}")
    print(f"{'─' * 70}")
    print(f"  Распределение по типам (для ИКАН):")
    for type_name, count in stats["by_type"].items():
        print(f"    • {type_name}: {count}")
    print(f"{'=' * 70}")


def generate_report(data: Dict, duplicates: Dict, stats: Dict, 
                    output_path: Path = None) -> Dict:
    """Генерация отчёта о валидации в формате JSON."""
    report = {
        "validation_status": "PASSED" if not (
            duplicates["within_subcategory"] or duplicates["within_cluster"]
        ) else "WARNINGS",
        "statistics": stats,
        "duplicates": duplicates,
        "summary": {
            "total_lexemes": stats["total_lexemes_unique"],
            "clusters": stats["total_clusters"],
            "subcategories": stats["total_subcategories"],
            "global_duplicates_count": len(duplicates["global"]),
            "internal_duplicates_count": (
                len(duplicates["within_subcategory"]) + 
                len(duplicates["within_cluster"])
            )
        }
    }
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n{OK} Отчёт сохранён: {output_path}")
    
    return report


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    """Основной поток валидации."""
    
    # Определение пути к файлу
    if len(sys.argv) > 1:
        ontology_path = Path(sys.argv[1])
    else:
        ontology_path = Path("data/ontology.json")
    
    print("\n" + "=" * 70)
    print("🔍 ВАЛИДАЦИЯ ОНТОЛОГИИ ТРАДИЦИОННЫХ ЦЕННОСТЕЙ")
    print("=" * 70)
    
    # Шаг 1: Загрузка
    success, data = load_ontology(ontology_path)
    if not success:
        sys.exit(1)
    
    # Шаг 2: Проверка метаданных
    if not validate_metadata(data):
        sys.exit(1)
    
    # Шаг 3: Проверка структуры
    structure_ok, errors = validate_structure(data)
    if not structure_ok:
        print(f"\n{ERR} ВАЛИДАЦИЯ СТРУКТУРЫ НЕ ПРОЙДЕНА")
        sys.exit(1)
    
    # Шаг 4: Поиск дубликатов
    duplicates = find_duplicates(data)
    
    # Шаг 5: Статистика
    stats = calculate_statistics(data)
    print_statistics(stats)
    
    # Шаг 6: Проверка соответствия заявленному количеству
    declared = data["metadata"].get("total_lexemes", 0)
    actual = stats["total_lexemes_unique"]
    
    print(f"\n{INFO} Проверка соответствия metadata:")
    if declared == actual:
        print(f"{OK} Заявленное количество ({declared}) совпадает с фактическим ({actual})")
    else:
        print(f"{WARN} Расхождение: заявлено {declared}, фактически {actual} "
              f"(разница: {actual - declared:+d})")
        print(f"{INFO} Рекомендуется обновить поле 'total_lexemes' в metadata")
    
    # Шаг 7: Генерация отчёта
    report_path = Path("validation_report.json")
    report = generate_report(data, duplicates, stats, report_path)
    
    # Финальный вердикт
    print(f"\n{'=' * 70}")
    if not duplicates["within_subcategory"] and not duplicates["within_cluster"]:
        print(f"✅ ВАЛИДАЦИЯ ПРОЙДЕНА УСПЕШНО")
        print(f"{'=' * 70}\n")
        sys.exit(0)
    else:
        print(f"⚠️  ВАЛИДАЦИЯ ЗАВЕРШЕНА С ПРЕДУПРЕЖДЕНИЯМИ")
        print(f"{'=' * 70}\n")
        sys.exit(2)  # Код 2 = есть предупреждения, но не критично


if __name__ == "__main__":
    main()
