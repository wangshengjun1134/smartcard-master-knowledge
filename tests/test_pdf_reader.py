"""测试 PDF 文档读取功能"""

from pathlib import Path

import pytest
import pypdfium2 as pdfium


class TestPDFReader:
    """PDF 读取测试"""

    @pytest.fixture
    def sample_pdf(self):
        """获取测试用的 PDF 文件路径"""
        pdf_path = Path("specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf")
        if not pdf_path.exists():
            pytest.skip(f"测试文件不存在: {pdf_path}")
        return pdf_path

    def test_read_pdf_all_pages(self, sample_pdf):
        """测试读取 PDF 全部内容"""
        print(f"\n读取 PDF: {sample_pdf}")

        # 使用 pypdfium2 打开 PDF
        pdf = pdfium.PdfDocument(str(sample_pdf))
        total_pages = len(pdf)
        print(f"总页数: {total_pages}")

        # 读取所有页面
        all_text = []
        for page_idx in range(total_pages):
            page = pdf.get_page(page_idx)
            text_page = page.get_textpage()
            text = text_page.get_text_bounded()
            all_text.append(text)
            text_page.close()
            page.close()

        pdf.close()

        full_text = "\n".join(all_text)
        print(f"内容长度: {len(full_text)} 字符")
        print(f"内容预览:\n{full_text[:500]}...")

        assert len(full_text) > 0

    def test_read_pdf_specific_page(self, sample_pdf):
        """测试读取 PDF 指定页内容"""
        print(f"\n读取 PDF 第 1 页: {sample_pdf}")

        pdf = pdfium.PdfDocument(str(sample_pdf))
        total_pages = len(pdf)

        page_number = 1
        if page_number <= total_pages:
            page = pdf.get_page(page_number - 1)
            text_page = page.get_textpage()
            page_text = text_page.get_text_bounded()
            text_page.close()
            page.close()

            print(f"第 {page_number} 页内容:\n{page_text[:500]}...")
            assert len(page_text) > 0
        else:
            pytest.skip(f"文档只有 {total_pages} 页")

        pdf.close()

    def test_read_pdf_page_range(self, sample_pdf):
        """测试读取 PDF 页面范围"""
        print(f"\n读取 PDF 第 1-3 页: {sample_pdf}")

        pdf = pdfium.PdfDocument(str(sample_pdf))
        total_pages = len(pdf)
        start_page = 1
        end_page = min(3, total_pages)

        for i in range(start_page - 1, end_page):
            page = pdf.get_page(i)
            text_page = page.get_textpage()
            page_text = text_page.get_text_bounded()
            text_page.close()
            page.close()

            print(f"\n--- 第 {i + 1} 页 ---")
            print(f"{page_text[:300]}...")

        pdf.close()


def test_pdf_read_first_page():
    """独立测试函数：读取 PDF 第一页"""
    pdf_path = Path("specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf")

    if not pdf_path.exists():
        print(f"PDF 文件不存在: {pdf_path}")
        return

    print(f"读取 PDF: {pdf_path}")

    pdf = pdfium.PdfDocument(str(pdf_path))
    total_pages = len(pdf)
    print(f"总页数: {total_pages}")

    # 读取第一页
    first_page = pdf.get_page(0)
    text_page = first_page.get_textpage()
    page_text = text_page.get_text_bounded()
    text_page.close()
    first_page.close()
    pdf.close()

    print(f"第一页内容:\n{page_text}")


def test_docling_read_specific_page():
    """使用 DoclingPDFProcessor 工具包读取 PDF 指定页"""
    from pathlib import Path
    from smartcard_kb.document import DoclingPDFProcessor

    pdf_path = Path("specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf")
    if not pdf_path.exists():
        print(f"PDF 文件不存在: {pdf_path}")
        return

    print(f"\n使用 DoclingPDFProcessor 读取: {pdf_path}")

    # 初始化工具类
    processor = DoclingPDFProcessor(do_ocr=True)

    # 处理前 5 页
    results = processor.process_pdf(str(pdf_path), page_range=(1, 5))

    # 打印结果预览
    print(f"共提取 {len(results)} 个结构化元素")
    for i, item in enumerate(results[:5]):
        print(f"\n--- 元素 {i + 1} ---")
        print(f"类型: {item['type']}")
        print(f"页码: {item['page']}")
        print(f"标题路径: {' > '.join(item['heading_path'])}")
        print(f"内容预览: {item['text'][:200]}...")


if __name__ == "__main__":
    test_pdf_read_first_page()
