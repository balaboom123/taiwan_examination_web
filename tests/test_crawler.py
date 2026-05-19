import unittest

from app.crawler import make_download_url, make_result_url, parse_result_page, parse_search_page


SEARCH_HTML = """
<html><body>
  <select name="ctl00$holderContent$wUctlExamYearStart$ddlExamYear">
    <option value="2026">115</option>
    <option selected="selected" value="2025">114</option>
    <option value="2024">113</option>
  </select>
  <select name="ctl00$holderContent$ddlExamCode" id="ctl00_holderContent_ddlExamCode">
    <option value="">所有考試簡稱...</option>
    <option value="114170">114年第三次專門職業及技術人員高等考試護理師考試</option>
    <option value="114160">114年專門職業及技術人員高等考試心理師考試</option>
  </select>
</body></html>
"""


RESULT_HTML = """
<html><body>
  <table id="ctl00_holderContent_tblExamQand">
    <tr>
      <td></td>
      <td>115年第一次專門職業及技術人員高等考試營養師、護理師、社會工作師考試</td>
      <td><a href="wHandExamQandA_File.ashx?t=B&amp;code=115030">盲用電腦專用試題</a></td>
      <td><a href="wHandExamQandA_File.ashx?t=A&amp;code=115030">本考試所有測驗題標準答案</a></td>
    </tr>
    <tr>
      <td></td><td></td><td></td><td>高等考試_護理師</td>
    </tr>
    <tr>
      <td></td><td></td><td></td>
      <td><a href="wHandExamQandA_File.ashx?t=Q&amp;code=115030&amp;c=101&amp;s=0101&amp;q=1">基礎醫學試題答案</a></td>
      <td><a href="wHandExamQandA_File.ashx?t=Q&amp;code=115030&amp;c=101&amp;s=0101&amp;q=1">試題</a></td>
      <td><a href="wHandExamQandA_File.ashx?t=S&amp;code=115030&amp;c=101&amp;s=0101&amp;q=1">答案</a></td>
      <td></td>
    </tr>
    <tr>
      <td></td><td></td><td></td>
      <td><a href="wHandExamQandA_File.ashx?t=Q&amp;code=115030&amp;c=101&amp;s=0102&amp;q=1">基本護理學試題答案更正答案</a></td>
      <td><a href="wHandExamQandA_File.ashx?t=Q&amp;code=115030&amp;c=101&amp;s=0102&amp;q=1">試題</a></td>
      <td><a href="wHandExamQandA_File.ashx?t=S&amp;code=115030&amp;c=101&amp;s=0102&amp;q=1">答案</a></td>
      <td><a href="wHandExamQandA_File.ashx?t=M&amp;code=115030&amp;c=101&amp;s=0102&amp;q=1">更正答案</a></td>
    </tr>
  </table>
</body></html>
"""


class ParseSearchPageTests(unittest.TestCase):
    def test_parse_search_page_extracts_years_and_exam_options(self) -> None:
        page = parse_search_page(SEARCH_HTML)

        self.assertEqual(page.available_years, [2026, 2025, 2024])
        self.assertEqual(page.exams[0].code, "114170")
        self.assertEqual(page.exams[0].year_ad, 2025)
        self.assertEqual(page.exams[0].year_roc, 114)
        self.assertIn("護理師", page.exams[0].label)


class ParseResultPageTests(unittest.TestCase):
    def test_parse_result_page_extracts_attachments_and_subject_files(self) -> None:
        parsed = parse_result_page(RESULT_HTML, exam_code="115030", year_ad=2026)

        self.assertEqual(parsed.exam_name_raw, "115年第一次專門職業及技術人員高等考試營養師、護理師、社會工作師考試")
        self.assertEqual(len(parsed.attachments), 2)
        self.assertEqual(parsed.attachments[0].file_type, "accessible_bundle")
        self.assertEqual(parsed.attachments[1].file_type, "all_answers")
        self.assertEqual(len(parsed.papers), 2)

        first_paper = parsed.papers[0]
        self.assertEqual(first_paper.category_raw, "高等考試_護理師")
        self.assertEqual(first_paper.category_code, "101")
        self.assertEqual(first_paper.subject_code, "0101")
        self.assertEqual(first_paper.subject_name_raw, "基礎醫學")
        self.assertEqual(set(first_paper.files), {"question", "answer"})

        second_paper = parsed.papers[1]
        self.assertEqual(second_paper.subject_name_raw, "基本護理學")
        self.assertEqual(set(second_paper.files), {"question", "answer", "corrected_answer"})

    def test_url_builders_return_live_http_entrypoints(self) -> None:
        self.assertEqual(
            make_result_url("115030", 2026),
            "https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx?e=115030&y=2026",
        )
        self.assertEqual(
            make_download_url("wHandExamQandA_File.ashx?t=Q&code=115030&c=101&s=0101&q=1"),
            "https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?t=Q&code=115030&c=101&s=0101&q=1",
        )


if __name__ == "__main__":
    unittest.main()
