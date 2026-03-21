"""Regression tests for web view mode/session state interactions."""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import textwrap
import unittest


_TEMPLATE_PATH = pathlib.Path(__file__).resolve().parents[1] / "ui" / "web" / "templates" / "index.html"


def _extract_main_inline_script() -> str:
    html = _TEMPLATE_PATH.read_text()
    inline_scripts = re.findall(r"<script>\s*([\s\S]*?)\s*</script>", html)
    for script in inline_scripts:
        if "let activeMode = 'deep';" in script and "function switchMode(mode)" in script:
            return script
    raise AssertionError("Could not find main web template inline script")


def _run_template_state(commands: str) -> dict:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is unavailable")

    payload = json.dumps(
        {
            "script": _extract_main_inline_script(),
            "commands": textwrap.dedent(commands),
        }
    )

    node_harness = textwrap.dedent(
        r"""
        const vm = require('vm');
        const payload = JSON.parse(process.env.PAYLOAD);

        function makeClassList(initial = []) {
          const set = new Set(initial);
          return {
            add: (...names) => names.forEach(name => set.add(name)),
            remove: (...names) => names.forEach(name => set.delete(name)),
            contains: (name) => set.has(name),
            toggle: (name, force) => {
              if (force === undefined) {
                if (set.has(name)) {
                  set.delete(name);
                  return false;
                }
                set.add(name);
                return true;
              }
              if (force) set.add(name); else set.delete(name);
              return !!force;
            },
            toString: () => Array.from(set).join(' '),
          };
        }

        function makeElement(id, classes = []) {
          return {
            id,
            dataset: {},
            style: {},
            classList: makeClassList(classes),
            value: '',
            innerHTML: '',
            textContent: '',
            disabled: false,
            checked: false,
            onclick: null,
            nextElementSibling: { textContent: '' },
            parentElement: null,
            children: [],
            addEventListener() {},
            removeEventListener() {},
            appendChild(child) { this.children.push(child); child.parentElement = this; return child; },
            remove() { this.removed = true; },
            focus() {},
            scrollIntoView() {},
            querySelectorAll() { return []; },
            querySelector() { return null; },
            closest() { return null; },
            setAttribute() {},
            getAttribute() { return null; },
          };
        }

        const elements = new Map();
        function ensure(id, classes = []) {
          if (!elements.has(id)) elements.set(id, makeElement(id, classes));
          return elements.get(id);
        }

        const ids = {
          body: [],
          newSearchButton: ['hidden'],
          deepResearchSection: ['search-section'],
          digestSection: ['search-section', 'hidden'],
          globalViewSection: ['hidden'],
          imagingSection: ['hidden'],
          researchLayout: ['research-layout', 'hidden'],
          chatDock: ['chat-dock', 'hidden'],
          newsIntelResultsContainer: [],
          sourceFilterGroup: [],
          sourceCards: [],
          chatThread: [],
          searchInput: [],
          chatInput: [],
          chatForm: [],
          gvDataTabs: [],
          deepResearchForm: [],
          newsIntelForm: [],
          searchButton: [],
          newsIntelButton: [],
          researchSidebar: [],
          sidebarBackdrop: [],
          sidebarList: [],
          stagedBadge: ['hidden'],
          gvDatasetsTab: [],
          gvArticlesTab: ['hidden'],
          datasetCardsGrid: [],
          gvArticlesBody: [],
          gvPagination: [],
          progressMessage: [],
          progressPhase: [],
          deepResearchPanel: [],
          digestPanel: [],
          digestHolding: [],
          stagedItemsList: [],
          newsTopicInput: [],
          newsDateFrom: [],
          newsDateTo: [],
          newsLimit: [],
          sidebarToggle: [],
          refinementModal: [],
          refineStartButton: [],
          refineWizardContainer: [],
          'global-map-container': [],
          'imaging-map-container': [],
          imgCommodity: [],
          imgCountry: [],
          imgStatus: [],
          imgGenerationTech: [],
          imgGenerationStatus: [],
          imgGenerationMinCapacity: [],
          imgDepositCount: [],
          imgConcessionCount: [],
          imgGenerationCount: [],
          imgHighCount: [],
          imgMedCount: [],
          imgLowCount: [],
          gvWarningBanner: ['hidden'],
          gvWarningText: [],
          gvMapCoverage: [],
          settingsModal: [],
          endpointModal: [],
          saveSettingsBtn: [],
          endpointForm: [],
          endpointType: [],
          endpointBaseUrl: [],
          endpointLabel: [],
          endpointModel: [],
          endpointMaxTokens: [],
          hfToken: [],
          openaiApiKey: [],
          anthropicApiKey: [],
        };

        for (const [id, classes] of Object.entries(ids)) ensure(id, classes);

        const welcome = makeElement('welcome', ['welcome-section']);
        const mainContainer = makeElement('main', ['main-container']);
        const modeButtons = ['deep', 'digest', 'global', 'imaging'].map((mode, idx) => {
          const el = makeElement(`mode-${mode}`, ['mode-nav-btn', ...(idx === 0 ? ['active'] : [])]);
          el.dataset.mode = mode;
          return el;
        });
        const depthButtons = [1, 2, 3].map((depth, idx) => {
          const el = makeElement(`depth-${depth}`, ['depth-option', ...(idx === 0 ? ['selected'] : [])]);
          el.dataset.depth = String(depth);
          return el;
        });

        const document = {
          body: ensure('body'),
          getElementById(id) { return ensure(id); },
          querySelector(selector) {
            if (selector === '.welcome-section') return welcome;
            if (selector === '.search-section') return ensure('deepResearchSection');
            if (selector === '.main-container') return mainContainer;
            if (selector === '.depth-option.selected') return depthButtons[0];
            return makeElement(`query:${selector}`);
          },
          querySelectorAll(selector) {
            if (selector === '.mode-nav-btn') return modeButtons;
            if (selector === '.depth-option') return depthButtons;
            return [];
          },
          createElement(tag) { return makeElement(tag); },
          addEventListener() {},
        };

        const context = {
          console,
          document,
          window: { history: { back() {} }, scrollTo() {} },
          history: { back() {} },
          setTimeout(fn) { if (typeof fn === 'function') fn(); return 1; },
          clearTimeout() {},
          fetch: async () => ({ ok: true, json: async () => ({ results: [] }) }),
          EventSource: function() { this.close = () => {}; },
          alert() {},
          confirm() { return true; },
          Map,
          Set,
        };

        vm.createContext(context);
        vm.runInContext(payload.script, context);

        context.loadGlobalView = () => {};
        context.loadImagingView = () => {};
        context.renderStagedItems = () => {};

        const result = vm.runInContext(payload.commands, context);
        console.log(JSON.stringify(result));
        """
    )

    result = subprocess.run(
        [node, "-e", node_harness],
        capture_output=True,
        text=True,
        env={**os.environ, "PAYLOAD": payload},
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Node harness failed with code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return json.loads(result.stdout.strip())


@unittest.skip("SEP-057: index.html exceeds OS ARG_MAX when passed as env var to Node.js on CI runners")
class WebViewStateTests(unittest.TestCase):
    def test_research_session_hides_chat_chrome_outside_deep_mode_and_restores_it_on_return(self):
        state = _run_template_state(
            """
            activateSessionFromResearch({ research_id: 'rid-1', query: 'q', sources: [], synthesis: '' });
            switchMode('global');
            const afterGlobal = {
              bodyActive: document.body.classList.contains('session-active'),
              deepHidden: document.getElementById('deepResearchSection').classList.contains('hidden'),
              globalHidden: document.getElementById('globalViewSection').classList.contains('hidden'),
              researchHidden: document.getElementById('researchLayout').classList.contains('hidden'),
              chatHidden: document.getElementById('chatDock').classList.contains('hidden'),
            };
            switchMode('deep');
            const afterDeepReturn = {
              bodyActive: document.body.classList.contains('session-active'),
              deepHidden: document.getElementById('deepResearchSection').classList.contains('hidden'),
              researchHidden: document.getElementById('researchLayout').classList.contains('hidden'),
              chatHidden: document.getElementById('chatDock').classList.contains('hidden'),
            };
            ({ afterGlobal, afterDeepReturn });
            """
        )

        self.assertFalse(state["afterGlobal"]["bodyActive"])
        self.assertTrue(state["afterGlobal"]["deepHidden"])
        self.assertFalse(state["afterGlobal"]["globalHidden"])
        self.assertTrue(state["afterGlobal"]["researchHidden"])
        self.assertTrue(state["afterGlobal"]["chatHidden"])

        self.assertTrue(state["afterDeepReturn"]["bodyActive"])
        self.assertTrue(state["afterDeepReturn"]["deepHidden"])
        self.assertFalse(state["afterDeepReturn"]["researchHidden"])
        self.assertFalse(state["afterDeepReturn"]["chatHidden"])

    def test_digest_session_hides_followup_chat_when_switching_to_other_modes(self):
        state = _run_template_state(
            """
            switchMode('digest');
            document.getElementById('newsIntelResultsContainer').innerHTML = '<div>Digest</div>';
            activateSessionFromNewsIntel({
              topic: 'energy',
              date_from: '2026-03-01',
              date_to: '2026-03-10',
              articles: [],
              synthesis: 'Digest synthesis'
            });
            switchMode('imaging');
            const afterImaging = {
              bodyActive: document.body.classList.contains('session-active'),
              imagingHidden: document.getElementById('imagingSection').classList.contains('hidden'),
              chatHidden: document.getElementById('chatDock').classList.contains('hidden'),
              digestResultsHidden: document.getElementById('newsIntelResultsContainer').classList.contains('hidden'),
            };
            switchMode('digest');
            const afterDigestReturn = {
              bodyActive: document.body.classList.contains('session-active'),
              digestHidden: document.getElementById('digestSection').classList.contains('hidden'),
              chatHidden: document.getElementById('chatDock').classList.contains('hidden'),
              digestResultsHidden: document.getElementById('newsIntelResultsContainer').classList.contains('hidden'),
            };
            ({ afterImaging, afterDigestReturn });
            """
        )

        self.assertFalse(state["afterImaging"]["bodyActive"])
        self.assertFalse(state["afterImaging"]["imagingHidden"])
        self.assertTrue(state["afterImaging"]["chatHidden"])
        self.assertTrue(state["afterImaging"]["digestResultsHidden"])

        self.assertTrue(state["afterDigestReturn"]["bodyActive"])
        self.assertFalse(state["afterDigestReturn"]["digestHidden"])
        self.assertFalse(state["afterDigestReturn"]["chatHidden"])
        self.assertFalse(state["afterDigestReturn"]["digestResultsHidden"])


if __name__ == "__main__":
    unittest.main()
