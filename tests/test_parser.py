import unittest

from customs import Ecosystem, parse_command


class PipTests(unittest.TestCase):
    def test_simple_package(self):
        r = parse_command("pip install requests")
        self.assertEqual([(d.ecosystem, d.name) for d in r.declarations], [(Ecosystem.PYPI, "requests")])
        self.assertIsNone(r.declarations[0].version)

    def test_pinned_version(self):
        r = parse_command("pip3 install Requests_Toolbelt==1.0.0")
        d = r.declarations[0]
        self.assertEqual(d.name, "requests-toolbelt")
        self.assertEqual(d.version, "1.0.0")

    def test_extras_and_range_specifier(self):
        d = parse_command('pip install "uvicorn[standard]>=0.30"').declarations[0]
        self.assertEqual(d.name, "uvicorn")
        self.assertEqual(d.specifier, ">=0.30")
        self.assertIsNone(d.version)

    def test_python_dash_m_pip_and_flags(self):
        r = parse_command("python3 -m pip install --upgrade -i https://idx.example/simple flask")
        self.assertEqual([d.name for d in r.declarations], ["flask"])

    def test_requirements_file_is_reported_not_dropped(self):
        r = parse_command("pip install -r requirements.txt")
        self.assertEqual(r.declarations, [])
        self.assertEqual(len(r.unparsed), 1)
        self.assertIn("requirements.txt", r.unparsed[0])

    def test_url_requirement(self):
        d = parse_command("pip install https://example.com/pkg-1.0.whl").declarations[0]
        self.assertEqual(d.ecosystem, Ecosystem.PYPI)
        self.assertEqual(d.name, "https://example.com/pkg-1.0.whl")

    def test_editable_git_install(self):
        d = parse_command("pip install -e git+https://github.com/owner/repo.git#egg=repo").declarations[0]
        self.assertEqual(d.ecosystem, Ecosystem.GIT)
        self.assertEqual(d.name, "github.com/owner/repo")


class NpmTests(unittest.TestCase):
    def test_unscoped_with_version(self):
        d = parse_command("npm install left-pad@1.3.0").declarations[0]
        self.assertEqual((d.ecosystem, d.name, d.version), (Ecosystem.NPM, "left-pad", "1.3.0"))

    def test_scoped_package(self):
        d = parse_command("npm i @scope/tool").declarations[0]
        self.assertEqual(d.name, "@scope/tool")
        self.assertEqual(d.specifier, "")

    def test_scoped_with_tag(self):
        d = parse_command("pnpm add -D @scope/tool@latest").declarations[0]
        self.assertEqual(d.name, "@scope/tool")
        self.assertEqual(d.specifier, "latest")
        self.assertIsNone(d.version)

    def test_bare_install_declares_nothing(self):
        self.assertEqual(parse_command("npm install").declarations, [])

    def test_github_shorthand_is_git(self):
        d = parse_command("npm install owner/repo").declarations[0]
        self.assertEqual((d.ecosystem, d.name), (Ecosystem.GIT, "github.com/owner/repo"))

    def test_local_path_is_unparsed(self):
        r = parse_command("npm install ./vendor/pkg")
        self.assertEqual(r.declarations, [])
        self.assertEqual(len(r.unparsed), 1)


class GitTests(unittest.TestCase):
    def test_clone_https_with_options(self):
        d = parse_command("git clone --depth 1 https://github.com/Owner/Repo.git work").declarations[0]
        self.assertEqual((d.ecosystem, d.name), (Ecosystem.GIT, "github.com/Owner/Repo"))

    def test_clone_scp_style(self):
        d = parse_command("git clone git@github.com:owner/repo.git").declarations[0]
        self.assertEqual(d.name, "github.com/owner/repo")

    def test_gh_repo_clone(self):
        d = parse_command("gh repo clone owner/repo").declarations[0]
        self.assertEqual(d.name, "github.com/owner/repo")


class SkillTests(unittest.TestCase):
    def test_skill_add_via_npx(self):
        d = parse_command("npx skills add https://github.com/owner/skill-pack").declarations[0]
        self.assertEqual(d.ecosystem, Ecosystem.SKILL)
        self.assertEqual(d.name, "https://github.com/owner/skill-pack")


class ChainTests(unittest.TestCase):
    def test_chained_commands_each_parsed(self):
        r = parse_command("pip install flask && npm i left-pad ; git clone https://github.com/a/b")
        names = [(d.ecosystem, d.name) for d in r.declarations]
        self.assertEqual(names, [
            (Ecosystem.PYPI, "flask"),
            (Ecosystem.NPM, "left-pad"),
            (Ecosystem.GIT, "github.com/a/b"),
        ])

    def test_unrelated_commands_declare_nothing(self):
        r = parse_command("ls -la && python3 app.py")
        self.assertEqual(r.declarations, [])
        self.assertEqual(r.unparsed, [])


if __name__ == "__main__":
    unittest.main()
