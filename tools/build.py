import os
import json
from datetime import datetime
from pathlib import Path
import zipfile
import subprocess
import shutil
import hashlib

config = {
    "module_name": "AIChat",                   # 模块名称
    "github_username": "wsu2059q",         # 你的 GitHub 用户名
    "official_repo": "ErisPulse/ErisPulse-ModuleRepo", # 官方仓库地址（一般无需更改）
    "local_module_path": "AIChat",             # 本地模块文件夹路径
    "files_to_include": [                              # 需要包含的文件列表
        "AIChat/__init__.py",
        "AIChat/Core.py"
    ]
}

def run_cmd(cmd, check=True, cwd=None):
    print(f"[CMD] {cmd}")
    return subprocess.run(cmd, shell=True, check=check, cwd=cwd)

def calculate_file_hash(file_path, hash_algorithm="sha256"):
    hash_func = getattr(hashlib, hash_algorithm)()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def on_rm_error(func, path, exc_info):
    os.chmod(path, 0o777)
    func(path)

def is_gh_installed():
    try:
        subprocess.run("gh --version", shell=True, check=True, stdout=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def get_git_config(config_name, cwd):
    try:
        result = subprocess.run(
            f"git config --global {config_name}",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
            cwd=cwd
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

repo_owner, repo_name = config["official_repo"].split("/")
module_repo_dir = Path(repo_name)

# 确保 gh 安装
if not is_gh_installed():
    print("""
[ERROR] GitHub CLI (gh) 未安装。

请先安装 gh：
Windows: https://github.com/cli/cli/releases/latest
Linux: sudo apt install gh
macOS: brew install gh

安装完成后重新运行此脚本。
""")
    exit(1)

print("[INFO] 正在加载模块信息...")
init_file = Path(config["local_module_path"]) / "__init__.py"
content = init_file.read_text(encoding="utf-8")

import ast

def extract_module_metadata(content):
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                try:
                    value_dict = eval(compile(ast.Expression(body=node.value), filename='<string>', mode='eval'))
                    meta = value_dict.get("meta", {})
                    if isinstance(meta, dict) and "version" in meta and "name" in meta:
                        return value_dict
                except Exception:
                    continue
        return None
    except SyntaxError as e:
        print(f"[ERROR] __init__.py 语法错误：{e}")
        return None


# 使用方式
content = init_file.read_text(encoding="utf-8")
module_meta = extract_module_metadata(content)

if not module_meta:
    print("[ERROR] 未找到包含 name 和 version 的模块元信息")
    exit(1)

current_version = module_meta["meta"]["version"]
module_name = module_meta["meta"]["name"]

# 构建前先打包一次，用于计算当前内容哈希
temp_zip = Path("temp_build.zip")
with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for file in config["files_to_include"]:
        zipf.write(file, arcname=os.path.basename(file))

current_build_hash = calculate_file_hash(temp_zip)

# 检查是否已有 build_hash 注释
content_lines = content.splitlines()
try:
    build_hash_line = next(line for line in content_lines if line.startswith("# build_hash="))
    last_build_hash = build_hash_line.split('"')[1]
    if last_build_hash == current_build_hash:
        print("[ERROR] 当前构建内容与上一次一致，请修改模块内容后再继续。")
        exit(1)
except StopIteration:
    pass

print(f"[WARN] 当前模块版本：{current_version}")
print("[WARN] 注意：构建不会自动更新版本号，请确保你已手动更新版本后再继续。")
input("[ACTION] 按回车键继续...")

build_time = datetime.now().isoformat()

fork_repo = f"{config['github_username']}/{repo_name}"

# Fork 并克隆仓库
def ensure_fork(repo):
    username = config["github_username"]
    fork_repo = f"{username}/{repo.split('/')[-1]}"
    try:
        run_cmd(f"gh repo view {fork_repo}", check=True)
        print(f"[INFO] 已找到 fork 的仓库：{fork_repo}")
    except subprocess.CalledProcessError:
        print(f"[INFO] 正在为你 fork 官方仓库：{repo}")
        run_cmd(f"gh repo fork {repo} --clone=false")

ensure_fork(config["official_repo"])

print("[INFO] 克隆官方模块源仓库...")
module_repo_dir = Path(repo_name)

if module_repo_dir.exists():
    choice = input(f"检测到已存在的 {repo_name} 目录，是否强制删除？(y/n): ")
    if choice.lower() == 'y':
        print(f"[INFO] 正在强制删除目录：{repo_name}")
        try:
            shutil.rmtree(module_repo_dir, onerror=on_rm_error)
        except Exception as e:
            print(f"[ERROR] 删除目录失败（即使尝试强制删除）：{e}")
            exit(1)
    else:
        print(f"[INFO] 跳过删除现有目录，将继续使用当前目录内容。")
else:
    print(f"[INFO] 正在创建新目录：{repo_name}")

run_cmd(f"gh repo clone {fork_repo} {module_repo_dir}")

# 加载 map.json
print("[INFO] 加载官方 map.json...")
map_file = module_repo_dir / "map.json"
data = json.loads(map_file.read_text(encoding="utf-8"))

# 构造模块条目
module_name = config["module_name"]
module_entry = {
    "path": f"/{module_name}-{current_version}.zip",
    "meta": {
        "name": module_meta.get("meta", {}).get("name"),
        "version": module_meta.get("meta", {}).get("version"),
        "description": module_meta.get("meta", {}).get("description"),
        "author": module_meta.get("meta", {}).get("author"),
        "license": module_meta.get("meta", {}).get("license"),
        "homepage": module_meta.get("meta", {}).get("homepage")
    },
    "dependencies": module_meta.get("dependencies", {}),
    "build_time": build_time
}

# 替换或新增模块信息
data["modules"][module_name] = module_entry

# 写入 map.json
map_file.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

# 打包模块
print("[INFO] 打包模块...")
zip_name = f"{config['module_name']}-{current_version}.zip"
zip_path = Path(zip_name)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for file in config["files_to_include"]:
        zipf.write(file, arcname=os.path.basename(file))

# 复制文件
modules_dir = module_repo_dir / "modules"
modules_dir.mkdir(exist_ok=True)
dest_path = modules_dir / zip_path.name
shutil.copyfile(zip_path, dest_path)

# 设置 Git 用户信息
git_user_name = get_git_config("user.name", module_repo_dir)
git_user_email = get_git_config("user.email", module_repo_dir)

if git_user_name and git_user_email:
    use_current = input(f"[INFO] 检测到当前 Git 用户配置: {git_user_name} <{git_user_email}>，是否继续使用？(y/n): ")
    if use_current.lower() != "y":
        git_user_name = input("[INPUT] 请输入新的 Git 用户名: ").strip()
        git_user_email = input("[INPUT] 请输入新的 Git 邮箱: ").strip()
else:
    print("[INFO] 未检测到 Git 用户配置，请设置：")
    git_user_name = input("[INPUT] Git 用户名: ").strip()
    git_user_email = input("[INPUT] Git 邮箱: ").strip()

run_cmd(f"git config --global user.name \"{git_user_name}\"", cwd=module_repo_dir)
run_cmd(f"git config --global user.email \"{git_user_email}\"", cwd=module_repo_dir)

# 创建并推送新分支
branch_name = f"update-{module_name.lower()}-{current_version}"
print(f"[INFO] 创建并推送新分支: {branch_name}")
run_cmd(f"git checkout -b {branch_name}", cwd=module_repo_dir)
run_cmd(f"git add .", cwd=module_repo_dir)
run_cmd(f'git commit -m "Update {module_name} to v{current_version}"', cwd=module_repo_dir)
run_cmd(f"git push origin {branch_name}", cwd=module_repo_dir)

# 尝试向官方仓库提交 PR
print("[INFO] 正在尝试向官方仓库提交 Pull Request...")
pr_created = False
try:
    run_cmd([
        "gh", "pr", "create",
        "-R", config["official_repo"],
        "--title", f"Update {module_name} to v{current_version}",
        "--body", f"添加/更新 `{module_name}` 模块至 v{current_version}",
        "--base", "main",
        "--head", branch_name
    ], cwd=module_repo_dir)
    print("[SUCCESS] PR 已成功提交到官方仓库！")
    pr_created = True
except subprocess.CalledProcessError as e:
    print("[ERROR] 自动提交 PR 失败，请手动提交以下链接：")
    compare_url = f"https://github.com/{config['official_repo']}/compare/main...{config['github_username']}:{branch_name}?expand=1"
    print(f"🔗 手动提交 PR 链接：{compare_url}")

# 写入 build_hash 到 __init__.py
build_hash = calculate_file_hash(zip_path)
with open(init_file, "a", encoding="utf-8") as f:
    f.write(f'\n# build_hash="{build_hash}"\n')

# 构建完成，询问是否清理
clean_up = input("[ACTION] 是否清理构建过程中生成的临时文件？(y/n): ").lower()
if clean_up == "y":
    temp_files = [
        temp_zip, zip_path, module_repo_dir
    ]
    for file in temp_files:
        if file.exists():
            if file.is_dir():
                shutil.rmtree(file, onerror=on_rm_error)
            else:
                os.remove(file)
    print("[INFO] 已清理临时文件。")
else:
    print("[INFO] 跳过清理步骤。")

print("[INFO] 构建完成！")
