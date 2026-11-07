"""Distribution structure: no private-path dependencies or external symlinks."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LayoutTests(unittest.TestCase):
    def test_skills_have_frontmatter(self):
        skills = list((ROOT / 'skills').glob('*/SKILL.md'))
        self.assertTrue(skills)
        for path in skills:
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('---\n'), path)
            self.assertRegex(text, r'(?m)^name: [a-z0-9-]+$', path)
            self.assertRegex(text, r'(?m)^description: .+', path)

    def test_relative_markdown_links(self):
        for path in ROOT.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' in link or link.startswith(('#', 'mailto:')):
                    continue
                target = (path.parent / link.split('#')[0]).resolve()
                self.assertTrue(target.is_relative_to(ROOT), (path, link))
                self.assertTrue(target.exists(), (path, link))

    def test_no_external_links_or_machine_paths(self):
        # Construct the markers so this test is not its own positive match.
        markers = ['/' + 'workspace/', '/' + 'docker-share/', '/' + 'home/piuser/']
        for path in ROOT.rglob('*'):
            if path.is_symlink():
                self.assertTrue(path.resolve().is_relative_to(ROOT), path)
            if path.suffix in {'.py', '.md', '.json'}:
                text = path.read_text(encoding='utf-8')
                for marker in markers:
                    self.assertNotIn(marker, text, path)


if __name__ == '__main__':
    unittest.main()
