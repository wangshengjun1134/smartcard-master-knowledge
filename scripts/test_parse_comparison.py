"""对比 PDF 和 DOCX 解析结果并保存到文件"""

import sys
import json
import time
from pathlib import Path
from collections import Counter

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smartcard_kb.docs_compile.pdf_parser import PDFParser

PDF_PATH = r"D:\softdata\workspaces\buff\smartcard-master-knowledge\specs\03-management-provisioning\gsma\SGP.27\SGP.27-PP-Module-for-Application-Isolation-in-the-eUICC-v1.0.pdf"
DOCX_PATH = r"D:\softdata\workspaces\buff\smartcard-master-knowledge\specs\03-management-provisioning\gsma\SGP.27\SGP.27-PP-Module-for-Application-Isolation-in-the-eUICC-v1.0.docx"
OUTPUT_DIR = Path(r"D:\softdata\workspaces\buff\smartcard-master-knowledge\output\comparison")


def parse_file(file_path, doc_id):
    """解析文件并返回 items"""
    print(f"\n{'='*60}")
    print(f"正在解析: {Path(file_path).name}")
    print(f"{'='*60}")
    
    parser = PDFParser(do_ocr=False)  # 关闭 OCR 加快速度
    result = parser.parse_pdf(
        pdf_path=file_path,
        document_id=doc_id,
        output_dir="output/pictures_test"
    )
    return result["items"]


def save_items(items, file_path, label):
    """保存 items 到 JSON 文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存完整 JSON
    json_path = OUTPUT_DIR / f"{label}_sgp27_items.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ {label} 完整结果已保存: {json_path}")
    
    # 保存摘要文件（用于快速对比）
    summary_path = OUTPUT_DIR / f"{label}_sgp27_summary.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"{'='*60}\n")
        f.write(f"{label} 解析结果摘要\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"总 Item 数: {len(items)}\n")
        
        type_counter = Counter(item["label"] for item in items)
        f.write(f"\n类型分布:\n")
        for t, count in type_counter.most_common():
            f.write(f"  {t}: {count}\n")
        
        text_lengths = [len(item.get("text") or "") for item in items]
        f.write(f"\n文本长度:\n")
        f.write(f"  总字符数: {sum(text_lengths)}\n")
        f.write(f"  平均长度: {sum(text_lengths)/len(text_lengths):.1f}\n" if text_lengths else "  平均长度: 0\n")
        f.write(f"  最大长度: {max(text_lengths)}\n" if text_lengths else "")
        f.write(f"  最小长度: {min(text_lengths)}\n" if text_lengths else "")
        
        pages = set()
        for item in items:
            page_id = item.get("page_id", "")
            if page_id:
                pages.add(page_id)
        f.write(f"\n覆盖页数: {len(pages)}\n")
        
        # 前 5 个 items 详细预览
        f.write(f"\n{'='*60}\n")
        f.write(f"前 5 个 Items 详细预览\n")
        f.write(f"{'='*60}\n\n")
        for i, item in enumerate(items[:5]):
            f.write(f"[{i+1}] {item['label']} (page: {item.get('page_id', 'N/A')})\n")
            f.write(f"    ID: {item['id']}\n")
            f.write(f"    Order: {item.get('order_index')}\n")
            text = item.get("text") or ""
            f.write(f"    文本长度: {len(text)}\n")
            f.write(f"    文本内容:\n{text[:500]}\n")
            if len(text) > 500:
                f.write(f"    ... (截断，总长度 {len(text)} 字符)\n")
            f.write(f"\n{'-'*40}\n\n")
        
        # 后 3 个 items 预览
        f.write(f"\n{'='*60}\n")
        f.write(f"最后 3 个 Items 预览\n")
        f.write(f"{'='*60}\n\n")
        for i, item in enumerate(items[-3:]):
            idx = len(items) - 3 + i
            f.write(f"[{idx+1}] {item['label']} (page: {item.get('page_id', 'N/A')})\n")
            f.write(f"    ID: {item['id']}\n")
            text = item.get("text") or ""
            f.write(f"    文本长度: {len(text)}\n")
            f.write(f"    文本内容:\n{text[:500]}\n")
            if len(text) > 500:
                f.write(f"    ... (截断，总长度 {len(text)} 字符)\n")
            f.write(f"\n{'-'*40}\n\n")
    
    print(f"✅ {label} 摘要已保存: {summary_path}")
    return json_path, summary_path


def analyze_items(items, label):
    """分析 items 并打印统计"""
    print(f"\n{'='*60}")
    print(f"📊 {label} 解析结果统计")
    print(f"{'='*60}")
    
    total = len(items)
    print(f"总 Item 数: {total}")
    
    # 按类型统计
    type_counter = Counter(item["label"] for item in items)
    print(f"\n类型分布:")
    for t, count in type_counter.most_common():
        print(f"  {t}: {count}")
    
    # 文本长度统计
    text_lengths = [len(item.get("text") or "") for item in items]
    print(f"\n文本长度:")
    print(f"  总字符数: {sum(text_lengths)}")
    print(f"  平均长度: {sum(text_lengths)/len(text_lengths):.1f}" if text_lengths else "  平均长度: 0")
    print(f"  最大长度: {max(text_lengths)}" if text_lengths else "")
    print(f"  最小长度: {min(text_lengths)}" if text_lengths else "")
    
    # 页码分布
    pages = set()
    for item in items:
        page_id = item.get("page_id", "")
        if page_id:
            pages.add(page_id)
    print(f"\n覆盖页数: {len(pages)}")
    
    return {
        "total": total,
        "types": dict(type_counter),
        "total_text_len": sum(text_lengths),
        "avg_text_len": sum(text_lengths)/len(text_lengths) if text_lengths else 0,
        "pages": len(pages),
    }


def main():
    print("="*60)
    print("PDF vs DOCX 解析对比测试")
    print("="*60)
    
    # 解析 PDF
    pdf_items = parse_file(PDF_PATH, "test_pdf_sgp27")
    pdf_stats = analyze_items(pdf_items, "PDF")
    pdf_json, pdf_summary = save_items(pdf_items, PDF_PATH, "PDF")
    
    # 解析 DOCX
    docx_items = parse_file(DOCX_PATH, "test_docx_sgp27")
    docx_stats = analyze_items(docx_items, "DOCX")
    docx_json, docx_summary = save_items(docx_items, DOCX_PATH, "DOCX")
    
    # 生成对比报告
    print(f"\n{'='*60}")
    print("🔍 对比分析")
    print(f"{'='*60}")
    
    print(f"\n| 指标 | PDF | DOCX | 差异 |")
    print(f"|------|-----|------|------|")
    print(f"| 总 Item 数 | {pdf_stats['total']} | {docx_stats['total']} | {docx_stats['total'] - pdf_stats['total']} |")
    print(f"| 总字符数 | {pdf_stats['total_text_len']} | {docx_stats['total_text_len']} | {docx_stats['total_text_len'] - pdf_stats['total_text_len']} |")
    print(f"| 平均文本长度 | {pdf_stats['avg_text_len']:.1f} | {docx_stats['avg_text_len']:.1f} | {docx_stats['avg_text_len'] - pdf_stats['avg_text_len']:.1f} |")
    print(f"| 覆盖页数 | {pdf_stats['pages']} | {docx_stats['pages']} | {docx_stats['pages'] - pdf_stats['pages']} |")
    
    # 类型差异
    pdf_types = set(pdf_stats['types'].keys())
    docx_types = set(docx_stats['types'].keys())
    only_pdf = pdf_types - docx_types
    only_docx = docx_types - pdf_types
    
    if only_pdf:
        print(f"\n⚠️  PDF 独有类型: {only_pdf}")
    if only_docx:
        print(f"\n⚠️  DOCX 独有类型: {only_docx}")
    
    # 详细类型对比
    all_types = sorted(pdf_types | docx_types)
    print(f"\n详细类型对比:")
    print(f"{'类型':<25} {'PDF':>8} {'DOCX':>8} {'差异':>8}")
    print("-" * 55)
    for t in all_types:
        pdf_c = pdf_stats['types'].get(t, 0)
        docx_c = docx_stats['types'].get(t, 0)
        diff = docx_c - pdf_c
        print(f"{t:<25} {pdf_c:>8} {docx_c:>8} {diff:>+8}")
    
    # 保存对比报告
    diff_path = OUTPUT_DIR / "comparison_report.txt"
    with open(diff_path, 'w', encoding='utf-8') as f:
        f.write(f"{'='*60}\n")
        f.write(f"PDF vs DOCX 解析对比报告\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"测试文件: SGP.27-PP-Module-for-Application-Isolation-in-the-eUICC-v1.0\n")
        f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write(f"{'='*60}\n")
        f.write(f"核心指标对比\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"{'指标':<20} {'PDF':>10} {'DOCX':>10} {'差异':>10}\n")
        f.write(f"{'-'*55}\n")
        f.write(f"{'总 Item 数':<20} {pdf_stats['total']:>10} {docx_stats['total']:>10} {docx_stats['total'] - pdf_stats['total']:>+10}\n")
        f.write(f"{'总字符数':<20} {pdf_stats['total_text_len']:>10} {docx_stats['total_text_len']:>10} {docx_stats['total_text_len'] - pdf_stats['total_text_len']:>+10}\n")
        f.write(f"{'平均文本长度':<20} {pdf_stats['avg_text_len']:>10.1f} {docx_stats['avg_text_len']:>10.1f} {docx_stats['avg_text_len'] - pdf_stats['avg_text_len']:>+10.1f}\n")
        f.write(f"{'覆盖页数':<20} {pdf_stats['pages']:>10} {docx_stats['pages']:>10} {docx_stats['pages'] - pdf_stats['pages']:>+10}\n")
        
        f.write(f"\n{'='*60}\n")
        f.write(f"类型分布对比\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"{'类型':<25} {'PDF':>8} {'DOCX':>8} {'差异':>8}\n")
        f.write(f"{'-'*55}\n")
        for t in all_types:
            pdf_c = pdf_stats['types'].get(t, 0)
            docx_c = docx_stats['types'].get(t, 0)
            diff = docx_c - pdf_c
            f.write(f"{t:<25} {pdf_c:>8} {docx_c:>8} {diff:>+8}\n")
        
        if only_pdf or only_docx:
            f.write(f"\n{'='*60}\n")
            f.write(f"独有类型\n")
            f.write(f"{'='*60}\n\n")
            if only_pdf:
                f.write(f"PDF 独有: {', '.join(only_pdf)}\n")
            if only_docx:
                f.write(f"DOCX 独有: {', '.join(only_docx)}\n")
        
        f.write(f"\n{'='*60}\n")
        f.write(f"文件位置\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"PDF 完整结果: {pdf_json}\n")
        f.write(f"PDF 摘要: {pdf_summary}\n")
        f.write(f"DOCX 完整结果: {docx_json}\n")
        f.write(f"DOCX 摘要: {docx_summary}\n")
        f.write(f"对比报告: {diff_path}\n")
    
    print(f"\n✅ 对比报告已保存: {diff_path}")
    print(f"\n{'='*60}")
    print("✅ 对比完成!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
