import os
import json
import fnmatch
import sys
import base64
from pathlib import Path

def load_config(config_path=None):
    """Загрузка конфигурации из JSON файла"""
    if config_path is None:
        config_path = "makedump.json"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def should_include(name, include_patterns, exclude_patterns):
    """Проверяет, должен ли быть включен файл/папка по шаблонам"""
    # Проверка исключений
    for exclude in exclude_patterns:
        if fnmatch.fnmatch(name, exclude):
            return False
    
    # Если нет явных включений, включаем всё
    if not include_patterns:
        return True
    
    # Проверка включений
    for include in include_patterns:
        if fnmatch.fnmatch(name, include):
            return True
    
    return False

def get_tree_structure(root_dir, file_include_patterns, file_exclude_patterns, folder_exclude_patterns, prefix=""):
    """Рекурсивно строит древовидную структуру директорий и файлов"""
    result = []
    try:
        items = sorted(os.listdir(root_dir))
    except PermissionError:
        return result
    
    # Фильтруем папки - исключаем только по folder_exclude_patterns
    dirs = [item for item in items 
            if os.path.isdir(os.path.join(root_dir, item)) 
            and should_include(item, ["*"], folder_exclude_patterns)]
    
    # Фильтруем файлы - по file_include_patterns и file_exclude_patterns
    files = [item for item in items 
             if not os.path.isdir(os.path.join(root_dir, item)) 
             and should_include(item, file_include_patterns, file_exclude_patterns)]
    
    # Сортируем: сначала папки, потом файлы
    items = dirs + files
    
    pointers = ["├── "] * (len(items) - 1) + ["└── "]
    
    for pointer, item in zip(pointers, items):
        path = os.path.join(root_dir, item)
        rel_path = os.path.relpath(path, Path(root_dir).parent)
        
        result.append(f"{prefix}{pointer}{item}")
        
        if os.path.isdir(path):
            extension = "│   " if pointer == "├── " else "    "
            result.extend(get_tree_structure(
                path, 
                file_include_patterns, 
                file_exclude_patterns, 
                folder_exclude_patterns, 
                prefix + extension
            ))
    
    return result

def dump_folders(config, output_file):
    """Дамп структуры папок"""
    print(">>> FOLDERS >>>", file=output_file)
    
    for source in config['folders']['sources']:
        root = source['root']
        if root == ".":
            root = os.getcwd()
        
        # Для папок: включаем ВСЕ папки (кроме исключенных), но фильтруем файлы по шаблонам
        file_include = source.get('include', [])
        file_exclude = source.get('exclude', [])
        folder_exclude = source.get('exclude', [])  # Для папок используем только exclude
        
        output_template = config['folders']['output']
        
        # Если шаблон содержит древовидную структуру
        if "├──" in output_template or "└──" in output_template:
            tree_lines = get_tree_structure(root, file_include, file_exclude, folder_exclude)
            for line in tree_lines:
                print(line, file=output_file)
        else:
            # Обычный вывод плоского списка
            for dirpath, dirnames, filenames in os.walk(root):
                # Фильтруем папки
                dirnames[:] = [d for d in dirnames if should_include(d, ["*"], folder_exclude)]
                
                for dirname in dirnames:
                    full_path = os.path.join(dirpath, dirname)
                    rel_path = os.path.relpath(full_path, root)
                    
                    output_line = output_template
                    if "@.name" in output_line:
                        output_line = output_line.replace('@.name', dirname)
                    if "@.path" in output_line:
                        output_line = output_line.replace('@.path', rel_path)
                    print(output_line, file=output_file)

def dump_files(config, output_file):
    """Дамп содержимого файлов"""
    print(">>> FILES >>>", file=output_file)
    
    for source in config['files']['sources']:
        root = source['root']
        if root == ".":
            root = os.getcwd()
        
        include = source['include']
        exclude = source['exclude']
        
        for dirpath, dirnames, filenames in os.walk(root):
            for filename in filenames:
                if should_include(filename, include, exclude):
                    file_path = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(file_path, root)
                    
                    try:
                        # Пробуем прочитать как текстовый файл
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # Если не текстовый, читаем как бинарный и кодируем в base64
                        with open(file_path, 'rb') as f:
                            content = base64.b64encode(f.read()).decode('ascii')
                    
                    output = config['files']['output']
                    output = output.replace('@.name', rel_path)
                    output = output.replace('@.data', content)
                    print(output, file=output_file)

def main():
    """Основная функция"""
    # Парсинг аргументов
    config_path = None
    output_path = "output.txt"
    
    for arg in sys.argv[1:]:
        if arg.endswith('.json'):
            config_path = arg
        else:
            output_path = arg
    
    config = load_config(config_path)
    
    # Создание директории для выходного файла если нужно
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as output_file:
        dump_folders(config, output_file)
        dump_files(config, output_file)
    
    print(f"Дамп успешно создан: {output_path}")

if __name__ == "__main__":
    main()