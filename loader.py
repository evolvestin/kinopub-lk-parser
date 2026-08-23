# ruff: noqa
import os

exclude_files = [
    'loader.py',
    '.env',
    'bots.py',
    'functions.py',
    'GDrive.py',
    'image.py',
    'instagram.py',
    'test.py',
    'test3.py',
    'README.md',
    'person2.json',
    #'test queries.txt',
    'test q',
    'per.json',
    'emoji.db',
    'instagram_session.json',
    'kinopub_history — копия.db',
    'kinopub_history.db',
    'episode_history.txt',
    'collected_code.txt',
    'local.sqlite3',
    'test_data.json',
    'data.json',
    'favicon.ico',
    'logo.png',
    'test queries.txt',
]
exclude_dirs = [
    '.git',
    '.idea',
    'images',
    'fonts',
    '__pycache__',
    '.venv',
    '.ruff_cache',
    #'css',
    'img',
    #'js',
    'uc_browser_data_aux',
    'uc_browser_data_main',
    'data',
    'node_modules',
]
exclude_dir_paths = [
    'staticfiles/admin/js',
    'staticfiles/admin/css',
]

include_only_top_level_dirs = []


def get_project_root():  # type: ignore
    """Возвращает имя корневой папки проекта."""
    return os.path.basename(os.path.dirname(os.path.abspath(__file__)))


def collect_code():  # type: ignore
    """Собирает код из указанных директорий проекта."""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    result = []

    for root, dirs, files in os.walk(root_dir):
        rel_root = os.path.relpath(root, root_dir)

        normalized_root = rel_root.replace('\\', '/')

        if any(
            normalized_root == excluded or normalized_root.startswith(excluded + '/')
            for excluded in exclude_dirs
        ):
            dirs[:] = []
            continue

        if any(excluded_path in normalized_root for excluded_path in exclude_dir_paths):
            dirs[:] = []
            continue

        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in sorted(files):
            if file not in exclude_files:
                file_path = os.path.join(root, file)
                rel_path = os.path.join(
                    get_project_root(),
                    os.path.relpath(file_path, root_dir),
                )
                print(rel_path)
                try:
                    with open(file_path, encoding='utf-8') as f:
                        content = f.read()
                    result.append(f'\n\n===== {rel_path} =====\n{content}')
                except Exception:
                    pass
    return '\n'.join(result)


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f'Запуск сбора кода в директории: {script_dir}')
    print(f'Включая только папки верхнего уровня: {include_only_top_level_dirs}')

    code = collect_code()  # type: ignore

    header = """
You are an expert Senior Python Developer. 
**CRITICAL INSTRUCTION**: All your logic, planning, and explanations MUST be written in **RUSSIAN**. The code itself remains in English.

### RULES & CONSTRAINTS

1. **RESPONSE STRUCTURE (MANDATORY)**:
   - **Step 2: Code Implementation**: Provide the code blocks.

2. **CODE EDITING PRINCIPLES**:
   - **DRY Principle**: Strictly adhere to Don't Repeat Yourself. Reuse existing utils/classes.
   - **Targeted Output**: 
     - Do NOT output the entire file if only one function changed. 
     - Output ONLY the specific function, class, or code block that needs modification.
     - However, if the logic requires a large new feature, write the FULL implementation of that new feature.
   - **Completeness**: Even though you output snippets, the code inside the snippet must be complete and working. No placeholders like `... # rest of code`.
   - Follow existing code style, typing conventions, and architectural patterns already used in the project.

3. **PYTHON SPECIFIC RULES (CRITICAL)**:
   - **NO LOCAL IMPORTS**: It is STRICTLY FORBIDDEN to import modules inside a function/method to save space. 
   - **Global Imports**: If a new module is needed, show a separate block for the top of the file with the new imports, or explicitly state "Add `import X` to the top of file Y".

4. **FORMATTING**:
   - Use the format:
     `File: <filename>`
     `Scope: <function_name or "Top of file" or "New File">`
     ```python
     <code_here>
     ```
   - No diffs (---/+++). Only final working code blocks.
   - **LANGUAGE**: Explanations must be in **RUSSIAN**. Code identifiers remain unchanged.

5. **CODE COMMENTS POLICY (ZERO TOLERANCE)**:
   - **NO TRIVIAL COMMENTS**: Do NOT add explanatory comments that describe *what* the code is doing (e.g., `# Use new endpoint`, `# Loop through items`).
   - **EXCEPTION**: Comments are allowed for warnings or explaining complex/hacky business logic that is not readable from code alone.
   - **STRICT RULE**: If the code is readable, it must have NO comments.
   - ABSOLUTE PROHIBITION:
        It is STRICTLY FORBIDDEN to place:
        - conflicts between instructions
        - planning thoughts
        inside code comments.

        If there is a conflict (e.g. missing imports, architectural limitation),
        it MUST be described ONLY in Step 1 (Plan & Explanation),
        and the code in Step 2 must remain 100% clean and comment-free.

---------------------------------------------------------------------------------
Project Codebase:
"""

    output_file = os.path.join(script_dir, 'collected_code.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header + '\n' + code + '\n' * 10 + 'TASK:' + '\n' * 10)

    print(f'\nСбор кода завершен. Результат сохранен в файл: {output_file}')
