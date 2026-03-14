"""
GitHub 自动发布器
==================

将生成的综述和论文分析自动推送到 GitHub 仓库。

支持两种模式：
  1. 新建仓库（自动 init + remote add + push）
  2. 推送到已有仓库（git add + commit + push）

使用标准 git CLI（subprocess），无需额外 Python 库。

环境变量配置：
  GITHUB_REPO_URL  — 目标仓库 URL（例如 https://github.com/user/vla-survey.git）
                     或使用 SSH：git@github.com:user/vla-survey.git
  GITHUB_TOKEN     — Personal Access Token（仅 HTTPS 方式需要）
"""

import os
import subprocess
import shutil
import json
from pathlib import Path
from typing import Optional

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
REPO_LOCAL  = Path(__file__).parent.parent / "github_repo"  # 本地克隆目录


def _run(cmd: list[str], cwd: Optional[Path] = None, check: bool = True) -> str:
    """执行 shell 命令，返回 stdout"""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"命令失败：{' '.join(cmd)}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )
    return result.stdout.strip()


def _get_repo_url() -> Optional[str]:
    """从环境变量获取仓库 URL，支持注入 token"""
    repo_url = os.environ.get("GITHUB_REPO_URL", "")
    token    = os.environ.get("GITHUB_TOKEN", "")

    if not repo_url:
        return None

    # 如果是 HTTPS URL 且有 token，注入认证
    if repo_url.startswith("https://") and token:
        # https://user:token@github.com/user/repo.git
        without_https = repo_url[len("https://"):]
        return f"https://oauth2:{token}@{without_https}"

    return repo_url


def setup_repo(repo_url: Optional[str] = None) -> Path:
    """
    初始化本地 git 仓库

    如果 repo_url 有效，则克隆（或拉取）远程仓库；
    否则在本地初始化一个新仓库。

    返回：本地仓库路径
    """
    url = repo_url or _get_repo_url()

    if url:
        if REPO_LOCAL.exists() and (REPO_LOCAL / ".git").exists():
            print(f"🔄 拉取远程最新内容：{REPO_LOCAL}")
            try:
                _run(["git", "pull", "--rebase"], cwd=REPO_LOCAL)
            except RuntimeError:
                print("   ⚠ pull 失败（可能是首次推送），继续")
        else:
            print(f"📦 克隆仓库：{url}")
            REPO_LOCAL.parent.mkdir(parents=True, exist_ok=True)
            _run(["git", "clone", url, str(REPO_LOCAL)])
    else:
        # 本地初始化
        REPO_LOCAL.mkdir(parents=True, exist_ok=True)
        if not (REPO_LOCAL / ".git").exists():
            print(f"🆕 初始化本地 git 仓库：{REPO_LOCAL}")
            _run(["git", "init"], cwd=REPO_LOCAL)
            _run(["git", "checkout", "-b", "main"], cwd=REPO_LOCAL)

    return REPO_LOCAL


def copy_outputs_to_repo(repo_path: Path) -> list[Path]:
    """
    将 outputs/ 目录下的文件复制到仓库目录

    目录结构（仓库内）：
      surveys/         — 综述 Markdown 文件
      paper_analyses/  — 逐篇论文 JSON 分析
      README.md        — 自动生成的索引

    返回：复制的文件列表
    """
    copied: list[Path] = []

    # ── 复制综述文件 ───────────────────────────────────────────
    surveys_dst = repo_path / "surveys"
    surveys_dst.mkdir(exist_ok=True)
    surveys_src = OUTPUTS_DIR / "surveys"
    if surveys_src.exists():
        for f in surveys_src.glob("*.md"):
            dst = surveys_dst / f.name
            shutil.copy2(f, dst)
            copied.append(dst)
            print(f"   📄 {f.name} → surveys/")

    # ── 复制论文分析 ───────────────────────────────────────────
    analyses_dst = repo_path / "paper_analyses"
    analyses_dst.mkdir(exist_ok=True)
    analyses_src = OUTPUTS_DIR / "paper_analyses"
    if analyses_src.exists():
        for f in analyses_src.glob("*.json"):
            dst = analyses_dst / f.name
            shutil.copy2(f, dst)
            copied.append(dst)
        print(f"   📁 paper_analyses/：{len(list(analyses_src.glob('*.json')))} 篇")

    # ── 生成 README.md ─────────────────────────────────────────
    readme_path = _generate_readme(repo_path, surveys_dst, analyses_dst)
    copied.append(readme_path)
    print(f"   📖 README.md 已更新")

    return copied


def _generate_readme(
    repo_path: Path,
    surveys_dst: Path,
    analyses_dst: Path,
) -> Path:
    """自动生成仓库 README.md"""
    import time
    from vla_pipeline.vla_queries import SURVEY_TITLE

    # 收集综述文件列表
    survey_files = sorted(surveys_dst.glob("*.md"), reverse=True)
    survey_links = "\n".join(
        f"- [{f.name}](surveys/{f.name})" for f in survey_files
    ) or "（暂无综述文件）"

    # 统计论文分析数量
    n_analyses = len(list(analyses_dst.glob("*.json")))

    # 尝试从最新综述提取摘要
    latest_survey_preview = ""
    if survey_files:
        try:
            content = survey_files[0].read_text(encoding="utf-8")
            # 取前 500 字作为预览
            preview_lines = [
                l for l in content.split("\n")
                if l.strip() and not l.startswith("#") and not l.startswith(">")
            ]
            latest_survey_preview = " ".join(preview_lines[:5])[:300]
        except Exception:
            pass

    readme = f"""# {SURVEY_TITLE}

> 🤖 由 Claude Opus 4.6 自动生成 · 最后更新：{time.strftime('%Y-%m-%d')}

本仓库收录 VLA（Vision-Language-Action）与具身智能领域的论文分析与自动综述，
覆盖 **{n_analyses} 篇** arXiv 论文，使用 Claude Batches API 批量分析生成。

## 📄 综述文档

{survey_links}

## 📊 论文分析

[paper_analyses/](paper_analyses/) 目录包含每篇论文的结构化 JSON 分析，字段包括：
- `one_sentence_summary`：一句话概括
- `key_contributions`：核心贡献
- `technical_approach`：技术方法
- `survey_theme`：主题分类
- `importance_score`：重要程度评分（1-5）

## 🔍 覆盖方向

| 方向 | 说明 |
|------|------|
| VLA核心架构 | Vision-Language-Action Models |
| 基础模型迁移 | Foundation Models for Robotics |
| 操作策略学习 | Robot Manipulation Policies |
| 视觉表示学习 | Visual Representation Learning |
| 任务规划推理 | LLM-based Task Planning |
| 数据与基准 | Datasets and Benchmarks |

## ⚙️ 生成方式

本仓库由 [`research-agent`](https://github.com) 自动生成：
1. 从 arXiv 收集论文
2. 使用 Claude Batches API（5折）批量分析
3. 使用 Claude Opus 4.6 + Streaming 生成综述
4. 自动推送到本仓库

---

*本仓库内容由 AI 自动生成，供学习参考，请结合原始论文进行研究。*
"""

    readme_path = repo_path / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    return readme_path


def commit_and_push(
    repo_path: Path,
    commit_message: Optional[str] = None,
) -> bool:
    """
    提交并推送到远程仓库

    返回：是否成功推送到远程
    """
    import time

    if not commit_message:
        commit_message = f"chore: 自动更新论文分析与综述 [{time.strftime('%Y-%m-%d %H:%M')}]"

    # 配置 git 用户（如未配置）
    try:
        _run(["git", "config", "user.email"], cwd=repo_path, check=False)
    except Exception:
        pass
    _run(["git", "config", "--local", "user.name",  "VLA Research Bot"], cwd=repo_path)
    _run(["git", "config", "--local", "user.email", "bot@research-agent.local"], cwd=repo_path)

    # 添加所有文件
    _run(["git", "add", "."], cwd=repo_path)

    # 检查是否有改动
    status = _run(["git", "status", "--porcelain"], cwd=repo_path)
    if not status:
        print("📭 没有新内容需要提交")
        return True

    # 提交
    print(f"📝 提交：{commit_message}")
    _run(["git", "commit", "-m", commit_message], cwd=repo_path)

    # 推送
    repo_url = _get_repo_url()
    if repo_url:
        # 确保 remote 已配置
        remotes = _run(["git", "remote"], cwd=repo_path, check=False)
        if "origin" not in remotes.split():
            _run(["git", "remote", "add", "origin", repo_url], cwd=repo_path)

        print(f"🚀 推送到远程...")
        try:
            _run(["git", "push", "-u", "origin", "main"], cwd=repo_path)
            print("✅ 推送成功！")
            return True
        except RuntimeError as e:
            print(f"⚠ 推送失败：{e}")
            print("   提示：请检查 GITHUB_REPO_URL 和 GITHUB_TOKEN 是否正确配置")
            return False
    else:
        print("📌 未配置 GITHUB_REPO_URL，内容已提交到本地仓库")
        print(f"   本地路径：{repo_path}")
        return True


def publish(
    survey_path: Optional[Path] = None,
    commit_message: Optional[str] = None,
    repo_url: Optional[str] = None,
) -> bool:
    """
    完整发布流程：设置仓库 → 复制文件 → 提交推送

    参数:
        survey_path:    最新综述文件路径（可选，仅用于日志显示）
        commit_message: 自定义提交信息
        repo_url:       覆盖环境变量中的仓库 URL

    返回:
        是否成功
    """
    print(f"\n{'='*60}")
    print(f"🚀 开始发布到 GitHub...")
    print(f"{'='*60}")

    # 设置仓库
    repo_path = setup_repo(repo_url)

    # 复制 outputs 到仓库
    print("\n📋 复制文件到仓库...")
    copied = copy_outputs_to_repo(repo_path)
    print(f"   共复制 {len(copied)} 个文件")

    # 提交并推送
    if survey_path:
        msg = commit_message or f"feat: 新增综述 {survey_path.name}"
    else:
        msg = commit_message

    success = commit_and_push(repo_path, msg)
    return success
