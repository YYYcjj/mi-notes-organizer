"""命令行入口"""
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import OrganizerConfig
from .models import NoteCollection
from .parsers import create_parser
from .organizers import NoteOrganizer
from .generators import MarkdownGenerator, SiteGenerator

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """📝 小米笔记内容整理工具 - 解析、清洗、分类、生成知识库"""
    pass


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="data/output", help="输出目录")
@click.option("--site/--no-site", default=True, help="生成静态站点")
@click.option("--title", default="我的笔记", help="站点标题")
def organize(source, output, site, title):
    """一键整理：解析 → 清洗 → 分类 → 生成

    SOURCE: 小米笔记导出文件 (ZIP/JSON/Markdown目录)
    """
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()

    config = OrganizerConfig(
        input_dir=source_path if source_path.is_dir() else source_path.parent,
        output_dir=output_path,
        site_dir=output_path / "site",
        site_title=title,
    )

    console.print(f"\n[bold cyan]📝 小米笔记整理工具[/bold cyan]")
    console.print(f"   输入: {source_path}")
    console.print(f"   输出: {output_path}")

    # 1. 解析
    console.print(f"\n[bold]🔍 步骤 1/4: 解析笔记...[/bold]")
    try:
        parser = create_parser(source_path, config)
        collection = parser.parse(source_path)
    except Exception as e:
        console.print(f"[red]❌ 解析失败: {e}[/red]")
        sys.exit(1)

    if collection.total_count == 0:
        console.print("[yellow]⚠️  没有找到笔记内容，请检查输入文件[/yellow]")
        sys.exit(0)

    console.print(f"   ✅ 成功解析 {collection.total_count} 条笔记")

    # 2. 整理
    console.print(f"\n[bold]🧹 步骤 2/4: 整理清洗...[/bold]")
    organizer = NoteOrganizer(config)
    collection = organizer.organize(collection)

    # 3. 生成 Markdown
    console.print(f"\n[bold]📄 步骤 3/4: 生成 Markdown...[/bold]")
    md_gen = MarkdownGenerator(config)
    md_gen.generate(collection)

    # 4. 生成站点
    if site:
        console.print(f"\n[bold]🌐 步骤 4/4: 生成静态站点...[/bold]")
        site_gen = SiteGenerator(config)
        site_gen.generate(collection)

    console.print(f"\n[bold green]✅ 全部完成！[/bold green]")


@cli.command()
@click.argument("source", type=click.Path(exists=True))
def parse(source):
    """仅解析笔记，显示预览"""
    source_path = Path(source).resolve()
    config = OrganizerConfig(input_dir=source_path)

    parser = create_parser(source_path, config)
    collection = parser.parse(source_path)

    console.print(f"\n[bold]共 {collection.total_count} 条笔记:[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim")
    table.add_column("标题")
    table.add_column("日期")
    table.add_column("字数")

    for i, note in enumerate(collection.notes[:50], 1):
        table.add_row(
            str(i),
            note.title[:50] + ("..." if len(note.title) > 50 else ""),
            note.date_str,
            str(note.word_count),
        )

    console.print(table)

    if collection.total_count > 50:
        console.print(f"\n   ... 还有 {collection.total_count - 50} 条笔记")


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="data/output", help="输出目录")
def markdown(source, output):
    """仅生成 Markdown 文件（不生成站点）"""
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()

    config = OrganizerConfig(
        input_dir=source_path if source_path.is_dir() else source_path.parent,
        output_dir=output_path,
    )

    parser = create_parser(source_path, config)
    collection = parser.parse(source_path)

    organizer = NoteOrganizer(config)
    collection = organizer.organize(collection)

    md_gen = MarkdownGenerator(config)
    md_gen.generate(collection)

    console.print(f"\n[bold green]✅ Markdown 文件已生成到: {output_path}[/bold green]")


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--title", default="我的笔记", help="站点标题")
def site(source, title):
    """仅生成静态站点"""
    source_path = Path(source).resolve()

    config = OrganizerConfig(
        input_dir=source_path if source_path.is_dir() else source_path.parent,
        site_title=title,
    )

    parser = create_parser(source_path, config)
    collection = parser.parse(source_path)

    organizer = NoteOrganizer(config)
    collection = organizer.organize(collection)

    site_gen = SiteGenerator(config)
    site_gen.generate(collection)


if __name__ == "__main__":
    cli()
