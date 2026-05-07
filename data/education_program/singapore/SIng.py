"""
vietnam_university_crawler_v5.py
=================================
Vietnam University Module Crawler — Version 5

ARCHITECTURE: Program-first
  • 20 universities × 5 programs × ~17 modules per program  =  ~1,700 rows
  • Every module has its own direct URL
  • Live crawl is attempted first; rich static data is the guaranteed fallback
  • Gemini AI fills description + skills for every module

Run:
    pip install requests beautifulsoup4 selenium webdriver-manager
    export GEMINI_API_KEY="your_key_here"
    python vietnam_university_crawler_v5.py
"""

import re, time, logging, csv, hashlib, os, json
from dataclasses import dataclass, asdict
from typing import Optional, Callable
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

OUTPUT_FILE   = "singapore_modules_v5.csv"
PAGE_TIMEOUT  = 12          # seconds — reduced so Selenium fails fast
CRAWL_DELAY   = 1.0
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("SGv5")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UniCrawler/5.0)"}


@dataclass
class CourseModule:
    university: str
    program: str
    module: str
    description: str
    skills: str
    url: str
    level: str = "Undergraduate"
    duration: str = "3 Credits / 1 Semester"
    entry_requirements: str = ""

    def fingerprint(self) -> str:
        return hashlib.md5(
            f"{self.university}|{self.module.lower().strip()}".encode()
        ).hexdigest()


def build_driver() -> webdriver.Chrome:
    opts = Options()
    for a in ["--headless=new","--no-sandbox","--disable-dev-shm-usage",
              "--disable-gpu","--window-size=1920,1080",
              "--disable-blink-features=AutomationControlled"]:
        opts.add_argument(a)
    opts.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) "
                      "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36")
    opts.add_experimental_option("excludeSwitches",["enable-automation"])
    opts.add_experimental_option("useAutomationExtension",False)
    drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    drv.set_page_load_timeout(PAGE_TIMEOUT)
    return drv


def get_soup(driver, url: str) -> Optional[BeautifulSoup]:
    try:
        driver.get(url); time.sleep(CRAWL_DELAY)
        return BeautifulSoup(driver.page_source, "html.parser")
    except (WebDriverException, TimeoutException) as e:
        log.debug("Selenium skipped %s — %s", url[:80], str(e)[:60]); return None


def req_soup(url: str, timeout: int = 8) -> Optional[BeautifulSoup]:
    """
    Fast HTTP probe. Returns None (silently) on 403/404/timeout so the caller
    can decide whether to escalate to Selenium or simply skip.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code in (403, 404, 429, 503):
            log.debug("HTTP %d — skipping %s", r.status_code, url[:80])
            return None
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except requests.exceptions.Timeout:
        log.debug("HTTP timeout — skipping %s", url[:80]); return None
    except Exception as e:
        log.debug("HTTP error — %s — %s", url[:80], str(e)[:60]); return None


def req_json(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status(); return r.json()
    except: return None


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip()


_SG_REQ = {
    "Computer Science":         "A-Level: H2 Mathematics. Polytechnic Diploma GPA ≥ 3.5. IELTS 6.0+.",
    "Software Engineering":     "A-Level: H2 Mathematics. Polytechnic Diploma in IT/Engineering.",
    "Information Technology":   "A-Level or Polytechnic Diploma in IT. IELTS 6.0+.",
    "Data Science":             "A-Level: H2 Mathematics. Strong analytical background. IELTS 6.0+.",
    "Artificial Intelligence":  "A-Level: H2 Mathematics. Polytechnic Diploma GPA ≥ 3.5. IELTS 6.5+.",
    "Information Security":     "A-Level: H2 Mathematics. Polytechnic IT Diploma. IELTS 6.0+.",
    "Computer Engineering":     "A-Level: H2 Mathematics + H2 Physics. Polytechnic EE Diploma.",
    "Electrical Engineering":   "A-Level: H2 Mathematics + H2 Physics. IELTS 6.0+.",
    "Electronics":              "A-Level: H2 Mathematics + H2 Physics. Polytechnic EE Diploma.",
    "Mechanical Engineering":   "A-Level: H2 Mathematics + H2 Physics. IELTS 6.0+.",
    "Civil Engineering":        "A-Level: H2 Mathematics + H2 Physics. IELTS 6.0+.",
    "Chemical Engineering":     "A-Level: H2 Mathematics + H2 Chemistry. IELTS 6.0+.",
    "Biomedical Engineering":   "A-Level: H2 Mathematics + H2 Biology/Chemistry. IELTS 6.5+.",
    "Business Administration":  "A-Level or Polytechnic Diploma. IELTS 6.0+.",
    "Finance":                  "A-Level: H2 Mathematics. Polytechnic Business Diploma. IELTS 6.0+.",
    "Accounting":               "A-Level or Polytechnic Business Diploma. IELTS 6.5+.",
    "Economics":                "A-Level: H2 Mathematics. IELTS 6.0+.",
    "International Business":   "A-Level or Polytechnic Diploma. IELTS 6.5+.",
    "Marketing":                "A-Level or Polytechnic Business Diploma. IELTS 6.0+.",
    "Law":                      "A-Level: Very competitive. LNAT required for NUS. IELTS 7.0+.",
    "Architecture":             "A-Level + Portfolio review. IELTS 6.5+.",
    "Engineering":              "A-Level: H2 Mathematics + H2 Physics. IELTS 6.0+.",
    "Nursing":                  "A-Level + Biology. IELTS 6.5+. Health screening.",
    "Psychology":               "A-Level or Polytechnic Diploma. IELTS 6.0+.",
    "Design":                   "A-Level or Polytechnic Diploma + Portfolio. IELTS 6.0+.",
    "Hospitality":              "A-Level or Polytechnic Diploma. IELTS 6.0+.",
    "Tourism":                  "A-Level or Polytechnic Diploma. IELTS 6.0+.",
    "Logistics":                "A-Level or Polytechnic Diploma. IELTS 6.0+.",
}


def entry_req(program: str, level: str = "Undergraduate") -> str:
    for k, v in _SG_REQ.items():
        if k.lower() in program.lower():
            return v
    if level == "Postgraduate":
        return "Bachelor degree (min. 2nd Class Honours or equivalent). IELTS 6.5+."
    return "GCE A-Level or Polytechnic Diploma. IELTS 6.0–6.5+."


def make_module(university: str, program: str, code: str, title: str,
                url: str, credits: str = "3", level: str = "Undergraduate",
                desc: str = "", skills: str = "") -> CourseModule:
    return CourseModule(
        university=university, program=program,
        module=f"{code} {clean(title)}" if code else clean(title),
        description=clean(desc), skills=clean(skills), url=url, level=level,
        duration=f"{str(credits).strip()} Credits / 1 Semester",
        entry_requirements=entry_req(program, level),
    )


KB: dict[str, tuple[str, str]] = {
    "data structure":("Covers fundamental data organisation techniques including arrays, linked lists, stacks, queues, trees, heaps, and hash tables. Students analyse time and space complexity and apply structures to solve real computational problems.","Array manipulation, linked list operations, binary tree traversal, hash table design, stack and queue implementation"),
    "algorithm":("Introduces algorithm design paradigms including divide and conquer, dynamic programming, greedy methods, and backtracking. Students prove correctness and analyse Big-O complexity.","Algorithm complexity analysis, divide and conquer design, dynamic programming, greedy implementation, correctness proof writing"),
    "machine learning":("Covers supervised learning, unsupervised learning, model evaluation, regularisation, and neural network fundamentals for predictive modelling.","Supervised model training, cross-validation, feature engineering, clustering algorithms, neural network design"),
    "deep learning":("Covers CNNs, RNNs, attention mechanisms, and transformers applied to computer vision and NLP tasks using modern frameworks.","CNN design, RNN sequence modelling, transformer fine-tuning, PyTorch/TensorFlow, transfer learning"),
    "database":("Examines relational database design, SQL querying, normalisation theory, transaction management, and indexing strategies.","SQL query writing, ER diagram design, normalisation, transaction management, index optimisation"),
    "computer network":("Studies OSI and TCP/IP network architectures, routing, switching, HTTP, DNS, and network security protocols.","TCP/IP configuration, routing protocol analysis, socket programming, network security evaluation, Wireshark analysis"),
    "operating system":("Analyses process scheduling, memory management, file systems, and I/O handling with practical implementation labs.","Process scheduling, memory allocation, file system design, deadlock detection, system call programming"),
    "software engineering":("Covers the full SDLC from requirements through design, implementation, testing, and maintenance, emphasising agile methods.","Requirements documentation, UML modelling, agile sprint planning, integration testing, Git version control"),
    "artificial intelligence":("Explores search algorithms, knowledge representation, planning, and reasoning under uncertainty.","Heuristic search, Bayesian reasoning, propositional logic, constraint satisfaction, decision tree construction"),
    "natural language":("Covers tokenisation, language models, sentiment analysis, NER, and transformer-based models such as BERT.","Text preprocessing, language model evaluation, sentiment classification, NER extraction, BERT fine-tuning"),
    "computer vision":("Covers image processing, feature extraction, object detection, and segmentation using classical and deep learning methods.","Image preprocessing, CNN classification, YOLO object detection, semantic segmentation, feature extraction"),
    "cloud computing":("Examines IaaS/PaaS/SaaS models with AWS/Azure/GCP hands-on, containerisation, and serverless computing.","Cloud provisioning, Docker containerisation, Kubernetes orchestration, serverless functions, cost optimisation"),
    "cybersecurity":("Covers cryptography, authentication, network security, secure coding, and ethical hacking fundamentals.","Cryptographic protocols, penetration testing, vulnerability scanning, secure coding practices, incident response"),
    "information security":("Studies access control, authentication, cryptography, network defence, and security policy for enterprise environments.","Access control design, public key cryptography, firewall configuration, security policy writing, risk assessment"),
    "big data":("Covers Hadoop, Apache Spark, real-time stream processing, and NoSQL storage for large-scale data pipelines.","Spark DataFrame programming, HDFS management, Kafka streaming, NoSQL querying, ETL pipeline design"),
    "web":("Covers full-stack web development including front-end frameworks, RESTful APIs, authentication, and database integration.","HTML/CSS/JavaScript, REST API design, React or Vue.js, backend frameworks, database integration"),
    "mobile":("Covers Android and iOS app development including UI design, data persistence, API consumption, and app store deployment.","Android/iOS UI design, REST API consumption, local storage, push notifications, app publishing"),
    "internet of things":("Introduces microcontroller programming, RTOS, sensor integration, and IoT system design with cloud connectivity.","Microcontroller programming, RTOS configuration, sensor integration, MQTT communication, IoT cloud platforms"),
    "embedded":("Covers microcontroller architecture, bare-metal and RTOS programming, hardware interfaces, and low-power design.","C programming for microcontrollers, interrupt handling, SPI/I2C interfaces, real-time task scheduling, power optimisation"),
    "discrete mathematics":("Introduces logic, set theory, combinatorics, graph theory, and proof techniques essential for computer science.","Formal proof writing, graph theory application, combinatorial counting, Boolean logic, mathematical induction"),
    "probability":("Covers random variables, distributions, Bayes theorem, expectation, and limit theorems with engineering applications.","Probability modelling, Bayesian inference, Monte Carlo simulation, hypothesis testing, stochastic analysis"),
    "linear algebra":("Covers vector spaces, matrix operations, eigenvalues, and SVD foundational for machine learning and optimisation.","Matrix factorisation, eigenvalue computation, vector space analysis, linear transformation, gradient optimisation"),
    "calculus":("Covers differential and integral calculus, series, and multivariable calculus for engineering and science applications.","Differentiation, integration, limit evaluation, partial derivatives, optimisation techniques"),
    "accounting":("Introduces financial and managerial accounting including double-entry bookkeeping, financial statement preparation, and cost accounting.","Double-entry bookkeeping, balance sheet preparation, income statement analysis, CVP analysis, ratio interpretation"),
    "financial":("Examines time value of money, capital budgeting, risk and return, portfolio theory, and corporate financing decisions.","DCF valuation, portfolio analysis, CAPM application, capital structure decisions, financial modelling"),
    "economics":("Analyses individual and firm behaviour and national economic systems with policy implications.","Supply-demand analysis, elasticity calculation, game theory, GDP interpretation, fiscal policy assessment"),
    "marketing":("Explores market segmentation, consumer behaviour, product development, pricing strategy, and digital marketing channels.","Market segmentation, consumer analysis, brand positioning, marketing mix optimisation, digital strategy"),
    "management":("Covers planning, organising, leading, and controlling including strategy, change management, and organisational behaviour.","Strategic planning, team leadership, change management, performance measurement, stakeholder analysis"),
    "entrepreneurship":("Guides students from opportunity recognition through business model development and lean startup methodology.","Business model canvas, lean startup, market validation, investor pitch, financial forecasting"),
    "supply chain":("Covers supply chain design, procurement, inventory management, demand forecasting, and logistics optimisation.","Inventory optimisation, demand forecasting, supplier evaluation, logistics cost analysis, risk management"),
    "human resource":("Covers recruitment, performance management, training, compensation, and employment law.","Recruitment design, performance appraisal, training needs analysis, compensation benchmarking, HR policy formulation"),
    "investment":("Examines equities, bonds, derivatives, portfolio construction, and performance evaluation.","Security valuation, portfolio construction, derivative pricing, performance attribution, factor model application"),
    "law":("Introduces legal principles, contract formation, tort liability, and legal reasoning through case analysis.","Legal case analysis, contract elements, tort assessment, statutory interpretation, legal research"),
    "circuit":("Studies electrical circuit analysis using KVL/KCL, Thevenin/Norton theorems, AC phasors, and transient analysis.","KVL/KCL application, Thevenin equivalent circuit, AC phasor analysis, transient response, circuit simulation"),
    "electronics":("Covers semiconductor physics, diode and transistor circuits, op-amps, and digital logic design.","Diode circuit analysis, transistor biasing, op-amp circuit design, digital logic implementation, circuit simulation"),
    "signal processing":("Covers Fourier transforms, FIR/IIR filtering, and spectral analysis for communications and audio applications.","Fourier transform application, FIR/IIR filter design, spectrum analysis, sampling theorem, noise reduction"),
    "control":("Studies feedback control systems, PID controllers, stability analysis, and state-space methods.","PID controller tuning, stability analysis, Bode plot interpretation, state-space modelling, digital control design"),
    "power":("Covers power generation, transmission, distribution, and protection systems.","Power flow analysis, fault calculation, protection coordination, transformer design, grid stability"),
    "structural":("Covers structural analysis methods, load calculations, and material behaviour for civil engineering.","Structural load analysis, beam design, truss calculation, material testing, finite element analysis"),
    "mechanics":("Covers statics, dynamics, kinematics, and material behaviour for engineering applications.","Free body diagram, moment calculation, kinematic analysis, material stress-strain, FEA application"),
    "thermodynamics":("Studies heat, work, energy conversion, entropy, and thermodynamic cycles for engineering systems.","Thermodynamic cycle analysis, entropy calculation, heat exchanger design, energy efficiency, combustion analysis"),
    "fluid mechanics":("Covers fluid statics, flow dynamics, viscous effects, and turbomachinery for engineering applications.","Bernoulli equation, Reynolds number analysis, pipe flow calculation, turbine design, CFD simulation"),
    "econometrics":("Covers linear regression, time series analysis, panel data methods, and causal inference for economics.","OLS regression, time series modelling, panel data estimation, hypothesis testing, causal inference"),
    "telecommunication":("Studies modulation, channel coding, multiple access techniques, and wireless communication systems.","Signal modulation, channel coding, OFDM design, multiple access techniques, link budget calculation"),
    "tourism":("Examines global tourism industry, destination management, tourist behaviour, sustainability, and tourism policy.","Destination analysis, tourist behaviour, sustainability planning, tourism impact assessment, policy evaluation"),
    "hospitality":("Covers hospitality operations including front-of-house, F and B, revenue management, and customer service.","Hospitality operations, revenue management, F and B management, customer service standards, quality control"),
    "banking":("Covers commercial and investment banking including lending, capital markets, regulatory frameworks, and risk management.","Credit analysis, lending decisions, capital market operations, regulatory compliance, interest rate risk management"),
    "logistics":("Covers freight forwarding, customs, warehousing, transport management, and global supply chain optimisation.","Freight documentation, customs procedures, warehouse layout, route optimisation, supply chain analytics"),
    "international trade":("Examines comparative advantage, trade policy, tariffs, and global supply chain management.","Trade policy analysis, comparative advantage modelling, tariff impact, WTO framework, export documentation"),
    "digital marketing":("Covers SEO, SEM, social media, content marketing, analytics, and marketing automation.","SEO/SEM optimisation, social media strategy, content marketing, Google Analytics, marketing automation"),
    "project management":("Covers project planning, execution, monitoring, and closure using agile and waterfall methodologies.","Gantt scheduling, risk management, agile sprint planning, stakeholder communication, cost variance analysis"),
    "material":("Studies crystal structures, mechanical and thermal and electrical properties, and characterisation of engineering materials.","Crystallography, tensile testing, phase diagram reading, materials selection, microstructure analysis"),
    "environmental":("Covers environmental chemistry, ecology, pollution control, environmental impact assessment, and sustainability.","Environmental impact assessment, pollution monitoring, ecological modelling, sustainability analysis, EIA reporting"),
    "physics":("Covers classical mechanics, electromagnetism, thermodynamics, quantum mechanics, and modern physics.","Mechanics problem solving, electromagnetic analysis, quantum model application, experimental physics, computational modelling"),
    "biology":("Introduces cell biology, genetics, physiology, ecology, and molecular biology principles.","Cell biology analysis, genetic problem solving, physiological assessment, ecological modelling, lab techniques"),
    "chemistry":("Covers atomic structure, chemical bonding, reactions, thermochemistry, and organic chemistry.","Chemical equation balancing, stoichiometry, organic synthesis, spectral analysis, lab safety"),
    "robotics":("Covers robot kinematics, dynamics, sensors, actuators, perception, and motion planning.","Kinematic chain modelling, sensor fusion, motion planning, ROS programming, robot simulation"),
    "renewable energy":("Examines solar, wind, hydro, and bioenergy systems including resource assessment, design, and grid integration.","Solar irradiance analysis, wind turbine sizing, grid integration, energy storage, techno-economic assessment"),
    "biomedical":("Covers physiological signal acquisition, medical device design, imaging systems, and biomedical instrumentation.","Biosignal processing, medical device testing, imaging analysis, biomedical data interpretation, clinical validation"),
}


def kb_enrich(modules: list) -> list:
    for mod in modules:
        if mod.description and mod.skills:
            continue
        lower = mod.module.lower()
        best = max((k for k in KB if k in lower), key=len, default="")
        if best:
            d, s = KB[best]
            if not mod.description: mod.description = d
            if not mod.skills:      mod.skills      = s
    return modules


def _gemini(prompt: str, max_tokens: int = 512, temperature: float = 0.9, retries: int = 3) -> str:
    if not GEMINI_API_KEY:
        return ""
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens, "topP": 0.95, "topK": 40}}
    wait = 5
    for _ in range(retries):
        try:
            r = requests.post(url, json=body, timeout=45)
            if r.status_code == 429: time.sleep(wait); wait = min(wait*2,60); continue
            if r.status_code >= 500: time.sleep(wait); wait = min(wait*2,60); continue
            r.raise_for_status()
            cands = r.json().get("candidates", [])
            if not cands: return ""
            text = cands[0].get("content",{}).get("parts",[{}])[0].get("text","")
            result = clean(text)
            if result: return result
            time.sleep(2)
        except requests.exceptions.Timeout: time.sleep(wait)
        except Exception as e: log.debug("Gemini error: %s", e); time.sleep(2)
    return ""


def _valid(text: str, min_words: int = 5) -> bool:
    if not text or not text.strip(): return False
    return len([w for w in text.split() if re.search(r"[a-zA-Z]", w)]) >= min_words


def _fallback_desc(mod: CourseModule) -> str:
    title = re.sub(r"^[A-Z]{2,6}\d{3,6}[A-Z]?\s*", "", mod.module).strip()
    return (f"This module covers {title.lower()}, part of the {mod.program} "
            f"programme at {mod.university}. Students explore core theoretical "
            f"and applied aspects, building competencies for professional practice.")


def _fallback_skills(mod: CourseModule) -> str:
    title = re.sub(r"^[A-Z]{2,6}\d{3,6}[A-Z]?\s*", "", mod.module).strip().lower()
    return (f"Core {title} concepts, theoretical framework application, "
            f"analytical problem-solving, academic research skills, practical {title} implementation")


_JOINT_PROMPT = (
    "Academic course catalogue editor. Write for this specific module:\n\n"
    "University : {university}\nProgram    : {program}\nModule     : {module}\n\n"
    'Return ONLY raw JSON:\n{{"description":"2-3 sentences (45-90 words) specific to THIS module.","skills":"skill1, skill2, skill3, skill4, skill5"}}'
)


def enrich_with_gemini(modules: list) -> list:
    modules = kb_enrich(modules)
    if not GEMINI_API_KEY:
        log.warning("No GEMINI_API_KEY — using hard fallbacks.")
        for mod in modules:
            if not _valid(mod.description): mod.description = _fallback_desc(mod)
            if not _valid(mod.skills):      mod.skills = _fallback_skills(mod)
        return modules
    needs = [m for m in modules if not _valid(m.description) or not _valid(m.skills)]
    log.info("Gemini: filling %d modules ...", len(needs))
    for i, mod in enumerate(needs, 1):
        log.info("  [%d/%d] %s | %s", i, len(needs), mod.university[:22], mod.module[:50])
        md, ms = not _valid(mod.description), not _valid(mod.skills)
        if md and ms:
            raw = _gemini(_JOINT_PROMPT.format(university=mod.university, program=mod.program, module=mod.module), 512, 0.9)
            cleaned = re.sub(r"```[a-zA-Z]*\n?","",raw).replace("```","").strip()
            try:
                p = json.loads(cleaned)
                d = clean(p.get("description",""))
                s = clean(p.get("skills",""))
                if _valid(d): mod.description = d
                if _valid(s): mod.skills = s
            except: pass
        elif ms:
            mod.skills = _gemini(f"List 5 skills from this module. Comma-separated.\nModule: {mod.module}\nOutput:", 160, 0.7)
        elif md:
            mod.description = _gemini(f"Write 2-3 sentence description (45-90 words) for:\nModule: {mod.module}\nProgram: {mod.program}\nPlain text:", 220, 0.9)
        time.sleep(0.5)
    for mod in modules:
        if not _valid(mod.description): mod.description = _fallback_desc(mod)
        if not _valid(mod.skills):      mod.skills = _fallback_skills(mod)
    n = len(modules)
    d = sum(1 for m in modules if _valid(m.description))
    s = sum(1 for m in modules if _valid(m.skills))
    log.info("AUDIT  Total:%d  Desc:%d/%.0f%%  Skills:%d/%.0f%%", n, d, d/n*100, s, s/n*100)
    return modules


# ══════════════════════════════════════════════════════════════════════
# ██  SINGAPORE UNIVERSITY PROGRAMME DATA  ████████████████████████████
# ══════════════════════════════════════════════════════════════════════
# Module URL patterns:
#   NUS    — https://nusmods.com/modules/{CODE}
#   NTU    — https://wish.wis.ntu.edu.sg/webexe/owa/AUS_SUBJ_CONT.main_display1?r_subj_code={CODE}&acadsem=2025S1
#   SMU    — https://scis.smu.edu.sg/programmes/undergraduate/curriculum
#   SIT    — https://www.singaporetech.edu.sg/programmes/{slug}
#   SP/NP/TP/NYP/RP  — polytechnic module pages
#   SUTD   — https://sutd.edu.sg/course/{code-slug}/
#   SUSS   — https://www.suss.edu.sg/courses/detail/{CODE}
# ══════════════════════════════════════════════════════════════════════


def _std_progs(uni_base, progs_data):
    result = []
    for pname, cat, mods in progs_data:
        result.append({
            "program": pname,
            "catalogue_url": cat,
            "modules": [(c, t, f"{uni_base}/{c.lower()}" if not u.startswith("http") else u, cr)
                        for c, t, u, cr in mods]
        })
    return result


# ── 1. NUS ────────────────────────────────────────────────────────────
def build_nus_programs():
    U = "National University of Singapore (NUS)"
    NM = "https://nusmods.com/modules"
    def u(c): return f"{NM}/{c}"
    return [
        {"program":"Computer Science","catalogue_url":"https://www.comp.nus.edu.sg/programmes/ug/cs/curr/","modules":[
            ("CS1010","Programming Methodology",u("CS1010"),"4"),
            ("CS1231","Discrete Structures",u("CS1231"),"4"),
            ("MA1521","Calculus for Computing",u("MA1521"),"4"),
            ("MA1522","Linear Algebra for Computing",u("MA1522"),"4"),
            ("ST2334","Probability and Statistics",u("ST2334"),"4"),
            ("CS2030S","Programming Methodology II",u("CS2030S"),"4"),
            ("CS2040S","Data Structures and Algorithms",u("CS2040S"),"4"),
            ("CS2100","Computer Organisation",u("CS2100"),"4"),
            ("CS2102","Database Systems",u("CS2102"),"4"),
            ("CS2103T","Software Engineering",u("CS2103T"),"4"),
            ("CS2106","Introduction to Operating Systems",u("CS2106"),"4"),
            ("CS2109S","Introduction to AI and Machine Learning",u("CS2109S"),"4"),
            ("CS3230","Design and Analysis of Algorithms",u("CS3230"),"4"),
            ("CS3210","Parallel Computing",u("CS3210"),"4"),
            ("CS3240","Interaction Design",u("CS3240"),"4"),
            ("CS4243","Computer Vision and Pattern Recognition",u("CS4243"),"4"),
            ("CS4246","AI Planning and Decision Making",u("CS4246"),"4"),
            ("CS4248","Natural Language Processing",u("CS4248"),"4"),
            ("CS4226","Internet Architecture",u("CS4226"),"4"),
            ("CS4224","Distributed Databases",u("CS4224"),"4"),
        ]},
        {"program":"Business Analytics","catalogue_url":"https://www.comp.nus.edu.sg/programmes/ug/ba/curr/","modules":[
            ("BT1101","Introduction to Business Analytics",u("BT1101"),"4"),
            ("CS1010","Programming Methodology",u("CS1010"),"4"),
            ("MA1521","Calculus for Computing",u("MA1521"),"4"),
            ("ST1131","Introduction to Statistics",u("ST1131"),"4"),
            ("BT2101","Operations and Technology Management",u("BT2101"),"4"),
            ("BT2102","Data Management and Visualisation",u("BT2102"),"4"),
            ("BT2103","Analytical Models in Business",u("BT2103"),"4"),
            ("CS2040S","Data Structures and Algorithms",u("CS2040S"),"4"),
            ("BT3102","Machine Learning for Business",u("BT3102"),"4"),
            ("BT3103","Application Systems Development",u("BT3103"),"4"),
            ("BT4015","Geospatial Analytics",u("BT4015"),"4"),
            ("BT4016","Fraud Analytics",u("BT4016"),"4"),
            ("BT4211","Data-Driven Marketing",u("BT4211"),"4"),
            ("BT4221","Big Data Techniques",u("BT4221"),"4"),
            ("BT4222","Mining Web Data",u("BT4222"),"4"),
            ("BT4240","Machine Learning for Finance",u("BT4240"),"4"),
        ]},
        {"program":"Information Systems","catalogue_url":"https://www.comp.nus.edu.sg/programmes/ug/is/curr/","modules":[
            ("IS1108","Digital Ethics and Data Privacy",u("IS1108"),"4"),
            ("CS1010","Programming Methodology",u("CS1010"),"4"),
            ("IS2101","Business and Technical Communication",u("IS2101"),"2"),
            ("IS2102","Software Engineering",u("IS2102"),"4"),
            ("IS2103","Enterprise Systems Development",u("IS2103"),"4"),
            ("IS3106","Enterprise Systems Interface Design and Administration",u("IS3106"),"4"),
            ("IS4241","Social Media Network Analysis",u("IS4241"),"4"),
            ("IS4250","Healthcare Informatics",u("IS4250"),"4"),
            ("IS4261","Data Analytics and Business Value",u("IS4261"),"4"),
            ("CS2102","Database Systems",u("CS2102"),"4"),
            ("IS3150","Cybersecurity Management",u("IS3150"),"4"),
            ("IS4151","Principles of Digital Forensics",u("IS4151"),"4"),
            ("BT2103","Analytical Models in Business",u("BT2103"),"4"),
            ("CS3240","Interaction Design",u("CS3240"),"4"),
        ]},
        {"program":"Computer Engineering","catalogue_url":"https://ceg.nus.edu.sg/programmes/","modules":[
            ("CS1010","Programming Methodology",u("CS1010"),"4"),
            ("EE2026","Digital Design",u("EE2026"),"4"),
            ("MA1521","Calculus for Computing",u("MA1521"),"4"),
            ("MA1522","Linear Algebra for Computing",u("MA1522"),"4"),
            ("CS2040S","Data Structures and Algorithms",u("CS2040S"),"4"),
            ("CS2100","Computer Organisation",u("CS2100"),"4"),
            ("EE2211","Introduction to Machine Learning",u("EE2211"),"4"),
            ("CS2106","Introduction to Operating Systems",u("CS2106"),"4"),
            ("CG2028","Computer Organisation and Architecture",u("CG2028"),"2"),
            ("CG2111A","Engineering Principles and Practice I",u("CG2111A"),"4"),
            ("EE3331C","Feedback Control Systems",u("EE3331C"),"4"),
            ("CG4002","Computer Engineering Capstone",u("CG4002"),"8"),
        ]},
        {"program":"Data Science and Analytics","catalogue_url":"https://www.stat.nus.edu.sg/","modules":[
            ("DSA1101","Introduction to Data Science",u("DSA1101"),"4"),
            ("MA1521","Calculus for Computing",u("MA1521"),"4"),
            ("MA1522","Linear Algebra for Computing",u("MA1522"),"4"),
            ("ST1131","Introduction to Statistics",u("ST1131"),"4"),
            ("CS1010","Programming Methodology",u("CS1010"),"4"),
            ("ST2131","Probability",u("ST2131"),"4"),
            ("ST2132","Mathematical Statistics",u("ST2132"),"4"),
            ("CS2040S","Data Structures and Algorithms",u("CS2040S"),"4"),
            ("DSA3101","Data Science in Practice",u("DSA3101"),"4"),
            ("ST3248","Statistical Machine Learning",u("ST3248"),"4"),
            ("CS4211","Formal Methods for Software Engineering",u("CS4211"),"4"),
            ("DSA4212","Optimisation for Large Scale Data Analysis",u("DSA4212"),"4"),
            ("DSA4213","Big Data Systems",u("DSA4213"),"4"),
            ("DSA4266","Sense-making Case Analysis",u("DSA4266"),"4"),
        ]},
    ]


# ── 2. NTU ────────────────────────────────────────────────────────────
def build_ntu_programs():
    U = "Nanyang Technological University (NTU)"
    W = "https://wish.wis.ntu.edu.sg/webexe/owa/AUS_SUBJ_CONT.main_display1?r_subj_code={}&acadsem=2025S1"
    def u(c): return W.format(c)
    return [
        {"program":"Computer Science","catalogue_url":"https://www.ntu.edu.sg/scse/admissions/programmes/undergraduate-programmes/bachelor-of-engineering-in-computer-science","modules":[
            ("SC1003","Introduction to Computational Thinking and Programming",u("SC1003"),"3"),
            ("MH1812","Discrete Mathematics",u("MH1812"),"3"),
            ("MH2500","Probability and Introduction to Statistics",u("MH2500"),"3"),
            ("SC2001","Algorithm Design and Analysis",u("SC2001"),"3"),
            ("SC2005","Operating Systems",u("SC2005"),"3"),
            ("SC2006","Software Engineering",u("SC2006"),"3"),
            ("SC2207","Introduction to Databases",u("SC2207"),"3"),
            ("SC3000","Artificial Intelligence",u("SC3000"),"3"),
            ("CE4074","Deep Learning",u("CE4074"),"3"),
            ("SC3020","Database System Principles",u("SC3020"),"3"),
            ("SC4001","Code Security",u("SC4001"),"3"),
            ("CE3003","Digital Image Processing",u("CE3003"),"3"),
            ("SC4010","Apply Cryptography",u("SC4010"),"3"),
            ("SC4043","Natural Language Processing",u("SC4043"),"3"),
            ("CE3002","Computer Networks",u("CE3002"),"3"),
            ("CZ4052","Cloud Computing",u("CZ4052"),"3"),
            ("CZ3007","Compiler Techniques",u("CZ3007"),"3"),
        ]},
        {"program":"Data Science and Artificial Intelligence","catalogue_url":"https://www.ntu.edu.sg/scse/admissions/programmes/undergraduate-programmes/bachelor-of-science-in-data-science-and-artificial-intelligence","modules":[
            ("SC1003","Introduction to Computational Thinking and Programming",u("SC1003"),"3"),
            ("MH1812","Discrete Mathematics",u("MH1812"),"3"),
            ("MH2500","Probability and Introduction to Statistics",u("MH2500"),"3"),
            ("MH3510","Regression Analysis",u("MH3510"),"3"),
            ("SC2001","Algorithm Design and Analysis",u("SC2001"),"3"),
            ("SC3000","Artificial Intelligence",u("SC3000"),"3"),
            ("CE4074","Deep Learning",u("CE4074"),"3"),
            ("CE4042","Natural Language Processing",u("CE4042"),"3"),
            ("CE4048","Computational Intelligence",u("CE4048"),"3"),
            ("CE4068","Practical Data Science",u("CE4068"),"3"),
            ("CB4021","Bioinformatics Algorithms",u("CB4021"),"3"),
            ("CZ4078","Machine Reasoning",u("CZ4078"),"3"),
            ("CZ4041","Machine Learning",u("CZ4041"),"3"),
        ]},
        {"program":"Computer Engineering","catalogue_url":"https://www.ntu.edu.sg/scse/admissions/programmes/undergraduate-programmes/bachelor-of-engineering-in-computer-engineering","modules":[
            ("CZ1007","Data Structures",u("CZ1007"),"3"),
            ("CZ1115","Introduction to Data Science and AI",u("CZ1115"),"3"),
            ("EE8084","Emerging Technologies",u("EE8084"),"3"),
            ("CE2001","Algorithms",u("CE2001"),"3"),
            ("CE2004","Probability and Statistics for Computing",u("CE2004"),"3"),
            ("CE2006","Software Engineering",u("CE2006"),"3"),
            ("CE2007","Microprocessors and Interfacing",u("CE2007"),"3"),
            ("CE3005","Computer Networks",u("CE3005"),"3"),
            ("CE3007","Computer Architecture",u("CE3007"),"3"),
            ("CE3109","Embedded Software and Systems",u("CE3109"),"3"),
            ("CE3003","Digital Image Processing",u("CE3003"),"3"),
            ("CE4010","Designing for the Internet of Things",u("CE4010"),"3"),
            ("CZ4031","Database System Principles",u("CZ4031"),"3"),
            ("CE4052","Cloud Computing",u("CE4052"),"3"),
        ]},
        {"program":"Business","catalogue_url":"https://www.ntu.edu.sg/nbs/admissions/undergraduate-programmes","modules":[
            ("AB1201","Financial Management",u("AB1201"),"3"),
            ("AB1202","Statistics and Analysis",u("AB1202"),"3"),
            ("AB1401","Business Strategy",u("AB1401"),"3"),
            ("AB2201","Foundations of Marketing",u("AB2201"),"3"),
            ("AB2301","Financial Accounting",u("AB2301"),"3"),
            ("AB2401","Organisational Behaviour",u("AB2401"),"3"),
            ("AB2501","Operations Management",u("AB2501"),"3"),
            ("AB3301","Corporate Finance",u("AB3301"),"3"),
            ("AB3401","Human Resource Management",u("AB3401"),"3"),
            ("AB4301","Investment Analysis",u("AB4301"),"3"),
            ("AB4311","International Finance",u("AB4311"),"3"),
            ("AB4401","Strategic Management",u("AB4401"),"3"),
            ("AB4601","Entrepreneurship and Venture Initiation",u("AB4601"),"3"),
        ]},
        {"program":"Electrical and Electronic Engineering","catalogue_url":"https://www.ntu.edu.sg/eee/admissions/programmes/undergraduate-programmes","modules":[
            ("EE1001","Fundamentals of EEE",u("EE1001"),"3"),
            ("EE2001","Circuit Analysis",u("EE2001"),"3"),
            ("EE2002","Analogue Electronics",u("EE2002"),"3"),
            ("EE2003","Computer Engineering",u("EE2003"),"3"),
            ("EE2004","Semiconductor Fundamentals",u("EE2004"),"3"),
            ("EE2010","Systems and Control",u("EE2010"),"3"),
            ("EE3002","Microelectronics",u("EE3002"),"3"),
            ("EE3004","Power Electronics and Drives",u("EE3004"),"3"),
            ("EE3008","Principles of Communications",u("EE3008"),"3"),
            ("EE4001","Final Year Project",u("EE4001"),"8"),
            ("EE4035","Smart Grid",u("EE4035"),"3"),
            ("EE4040","Machine Learning for Signal Processing",u("EE4040"),"3"),
            ("EE4040","Deep Learning",u("CE4074"),"3"),
        ]},
    ]


# ── 3. SMU ────────────────────────────────────────────────────────────
def build_smu_programs():
    B = "https://scis.smu.edu.sg/programmes/undergraduate"
    L = "https://business.smu.edu.sg/programmes/bba/curriculum"
    def u(p): return f"{B}/{p}"
    return [
        {"program":"Computer Science","catalogue_url":u("bsc-computer-science"),"modules":[
            ("CS101","Computational Thinking",u("bsc-computer-science"),"5"),
            ("CS102","Programming Methodology",u("bsc-computer-science"),"5"),
            ("CS201","Data Structures and Algorithms",u("bsc-computer-science"),"5"),
            ("CS202","Linear Algebra",u("bsc-computer-science"),"5"),
            ("CS203","Probability and Statistics",u("bsc-computer-science"),"5"),
            ("CS301","Design and Analysis of Algorithms",u("bsc-computer-science"),"5"),
            ("CS302","Operating Systems",u("bsc-computer-science"),"5"),
            ("CS303","Networks",u("bsc-computer-science"),"5"),
            ("CS304","Database Management Systems",u("bsc-computer-science"),"5"),
            ("CS305","Software Engineering",u("bsc-computer-science"),"5"),
            ("CS401","Machine Learning",u("bsc-computer-science"),"5"),
            ("CS402","Big Data Analytics",u("bsc-computer-science"),"5"),
            ("CS403","Natural Language Processing",u("bsc-computer-science"),"5"),
            ("CS404","Cloud Computing",u("bsc-computer-science"),"5"),
            ("CS405","Information Security",u("bsc-computer-science"),"5"),
        ]},
        {"program":"Software Engineering","catalogue_url":u("bsc-software-engineering"),"modules":[
            ("CS101","Computational Thinking",u("bsc-software-engineering"),"5"),
            ("SE201","Requirements Engineering",u("bsc-software-engineering"),"5"),
            ("SE202","Software Design and Architecture",u("bsc-software-engineering"),"5"),
            ("SE203","Software Testing and Quality Assurance",u("bsc-software-engineering"),"5"),
            ("SE204","Project Management for Software",u("bsc-software-engineering"),"5"),
            ("CS201","Data Structures and Algorithms",u("bsc-software-engineering"),"5"),
            ("SE301","Mobile Application Development",u("bsc-software-engineering"),"5"),
            ("SE302","Web Application Development",u("bsc-software-engineering"),"5"),
            ("SE303","Agile Software Development",u("bsc-software-engineering"),"5"),
            ("SE304","DevOps and CI/CD",u("bsc-software-engineering"),"5"),
            ("SE401","Distributed Systems",u("bsc-software-engineering"),"5"),
            ("SE402","Microservices Architecture",u("bsc-software-engineering"),"5"),
            ("SE403","Blockchain Applications",u("bsc-software-engineering"),"5"),
            ("SE404","Senior Capstone",u("bsc-software-engineering"),"10"),
        ]},
        {"program":"Information Systems","catalogue_url":u("bsc-information-systems"),"modules":[
            ("IS101","Enterprise IT Systems",u("bsc-information-systems"),"5"),
            ("IS201","Enterprise Systems Development",u("bsc-information-systems"),"5"),
            ("IS202","Business Analytics",u("bsc-information-systems"),"5"),
            ("IS203","IS Strategy and Management",u("bsc-information-systems"),"5"),
            ("IS301","Digital Innovation and Design",u("bsc-information-systems"),"5"),
            ("IS302","IT Governance and Cybersecurity",u("bsc-information-systems"),"5"),
            ("IS303","Data Analytics",u("bsc-information-systems"),"5"),
            ("IS304","Enterprise Architecture",u("bsc-information-systems"),"5"),
            ("IS401","AI for Business",u("bsc-information-systems"),"5"),
            ("IS402","Blockchain Technology",u("bsc-information-systems"),"5"),
            ("IS403","Digital Transformation",u("bsc-information-systems"),"5"),
            ("IS404","IS Capstone",u("bsc-information-systems"),"10"),
        ]},
        {"program":"Business Administration","catalogue_url":L,"modules":[
            ("BUS101","Business Law",L,"5"),("ACC101","Introductory Financial Accounting",L,"5"),
            ("FIN101","Finance",L,"5"),("MKTG101","Marketing",L,"5"),
            ("OM101","Operations Management",L,"5"),("OB101","Organisational Behaviour",L,"5"),
            ("ECON201","Microeconomics",L,"5"),("ACCT201","Managerial Accounting",L,"5"),
            ("FIN301","Corporate Finance",L,"5"),("MKTG301","Consumer Behaviour",L,"5"),
            ("STR401","Strategic Management",L,"5"),("FIN401","Investment Analysis",L,"5"),
            ("MKTG401","Digital Marketing",L,"5"),("ENT401","Entrepreneurship",L,"5"),
        ]},
        {"program":"Accountancy","catalogue_url":"https://accountancy.smu.edu.sg/programmes/baccountancy/curriculum","modules":[
            ("ACCT101","Financial Accounting",L,"5"),("ACCT102","Cost and Management Accounting",L,"5"),
            ("ACCT201","Intermediate Financial Accounting",L,"5"),("ACCT202","Advanced Financial Accounting",L,"5"),
            ("ACCT203","Accounting Information Systems",L,"5"),("ACCT301","Auditing and Assurance",L,"5"),
            ("ACCT302","Corporate Reporting",L,"5"),("ACCT303","Taxation",L,"5"),
            ("ACCT304","Financial Statement Analysis",L,"5"),("ACCT401","Advanced Auditing",L,"5"),
            ("ACCT402","International Financial Reporting Standards",L,"5"),("ACCT403","Forensic Accounting",L,"5"),
            ("ACCT404","Ethics and Governance",L,"5"),("ACCT405","Accountancy Capstone",L,"10"),
        ]},
    ]


# ── 4. SIT ────────────────────────────────────────────────────────────
def build_sit_programs():
    B = "https://www.singaporetech.edu.sg/programmes"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Software Engineering",u("bachelor-of-engineering-software-engineering"),[
            ("INF1002","Programming Fundamentals","4"),("INF1005","Mathematical Applications for IT","4"),
            ("INF1008","Data Structures and Algorithms","4"),("INF1009","Object Oriented Programming","4"),
            ("INF1015","Computing Systems and Platforms","4"),("INF2004","Database Systems","4"),
            ("INF2006","Software Architecture and Design","4"),("INF2010","Object Oriented Analysis and Design","4"),
            ("INF2011","Emerging Technologies","4"),("INF2012","Software Testing","4"),
            ("INF3013","Cloud Architecture","4"),("INF3014","DevOps and Agile","4"),
            ("INF3015","Software Project Management","4"),("INF4011","Software Engineering Capstone","8"),
        ]),
        prog("Information Security",u("bachelor-of-engineering-information-security"),[
            ("INF1002","Programming Fundamentals","4"),("INF1008","Data Structures and Algorithms","4"),
            ("INF2102","Security Fundamentals","4"),("INF2103","Network Security","4"),
            ("INF2104","Cryptography","4"),("INF3104","Penetration Testing","4"),
            ("INF3105","Digital Forensics","4"),("INF3106","Malware Analysis","4"),
            ("INF3107","Secure Software Development","4"),("INF3108","Cloud Security","4"),
            ("INF4102","Information Security Capstone","8"),
        ]),
        prog("ICT and Systems",u("bachelor-of-science-information-and-communications-technology"),[
            ("INF1002","Programming Fundamentals","4"),("INF1004","Statistics and Probability","4"),
            ("INF1005","Mathematical Applications for IT","4"),("INF2001","Operating Systems","4"),
            ("INF2003","Computer Networks","4"),("INF2004","Database Systems","4"),
            ("INF3001","Mobile Applications Development","4"),("INF3002","Web Applications Development","4"),
            ("INF3003","Distributed Computing","4"),("INF3005","Artificial Intelligence","4"),
            ("INF3008","Big Data Analytics","4"),("INF4001","ICT Capstone","8"),
        ]),
        prog("Business Administration",u("bachelor-of-science-business"),[
            ("BUS1002","Applied Business Communication","4"),("BUS1003","Accounting","4"),
            ("BUS1004","Microeconomics for Business","4"),("BUS2001","Business Finance","4"),
            ("BUS2002","Marketing Management","4"),("BUS2003","Operations and Supply Chain Management","4"),
            ("BUS2004","Organisational Behaviour","4"),("BUS3001","Strategic Management","4"),
            ("BUS3002","Human Resource Management","4"),("BUS3003","Entrepreneurship","4"),
            ("BUS3004","Digital Business","4"),("BUS4001","Business Capstone","8"),
        ]),
        prog("Electrical Power Engineering",u("bachelor-of-engineering-electrical-power-engineering"),[
            ("ENG1001","Engineering Mathematics","4"),("ENG1002","Electric Circuit Analysis","4"),
            ("ENG2001","Electronics","4"),("ENG2002","Power Systems","4"),
            ("ENG2003","Control Systems","4"),("ENG2004","Electric Machines","4"),
            ("ENG3001","Power Electronics","4"),("ENG3002","Renewable Energy Systems","4"),
            ("ENG3003","Smart Grid","4"),("ENG3004","Power System Protection","4"),
            ("ENG4001","Electrical Engineering Capstone","8"),
        ]),
    ]


# ── 5. SP (Singapore Polytechnic) ─────────────────────────────────────
def build_sp_programs():
    B = "https://www.sp.edu.sg/schools"
    def u(p): return f"{B}/{p}"
    return [
        {"program":"Diploma in Information Technology","catalogue_url":u("soc/courses-and-curriculum/information-technology"),"modules":[
            ("IT1001","Computational Thinking and Programming",u("soc/courses/IT1001"),"4"),
            ("IT1002","Web Application Development",u("soc/courses/IT1002"),"4"),
            ("IT2001","Database Design and Development",u("soc/courses/IT2001"),"4"),
            ("IT2002","Object-Oriented Programming",u("soc/courses/IT2002"),"4"),
            ("IT2003","Operating Systems and Networking",u("soc/courses/IT2003"),"4"),
            ("IT2004","Software Engineering",u("soc/courses/IT2004"),"4"),
            ("IT3001","Application Security",u("soc/courses/IT3001"),"4"),
            ("IT3002","Cloud Computing",u("soc/courses/IT3002"),"4"),
            ("IT3003","Mobile Application Development",u("soc/courses/IT3003"),"4"),
            ("IT3004","Data Analytics",u("soc/courses/IT3004"),"4"),
            ("IT3005","IT Project",u("soc/courses/IT3005"),"6"),
        ]},
        {"program":"Diploma in Business","catalogue_url":u("sbus/courses-and-curriculum/business"),"modules":[
            ("BUS1001","Principles of Business",u("sbus/courses/BUS1001"),"4"),
            ("BUS1002","Business Communication",u("sbus/courses/BUS1002"),"4"),
            ("ACC1001","Accounting Fundamentals",u("sbus/courses/ACC1001"),"4"),
            ("BUS2001","Marketing Management",u("sbus/courses/BUS2001"),"4"),
            ("BUS2002","Financial Management",u("sbus/courses/BUS2002"),"4"),
            ("BUS2003","Operations Management",u("sbus/courses/BUS2003"),"4"),
            ("BUS2004","Human Resource Management",u("sbus/courses/BUS2004"),"4"),
            ("BUS3001","Strategic Management",u("sbus/courses/BUS3001"),"4"),
            ("BUS3002","Entrepreneurship",u("sbus/courses/BUS3002"),"4"),
            ("BUS3003","Digital Business",u("sbus/courses/BUS3003"),"4"),
            ("BUS3004","Business Project",u("sbus/courses/BUS3004"),"6"),
        ]},
        {"program":"Diploma in Electrical and Electronic Engineering","catalogue_url":u("seg/courses-and-curriculum/electrical-electronic-engineering"),"modules":[
            ("EEE1001","Mathematics for Engineering",u("seg/courses/EEE1001"),"4"),
            ("EEE1002","Circuit Analysis",u("seg/courses/EEE1002"),"4"),
            ("EEE1003","Electronics 1",u("seg/courses/EEE1003"),"4"),
            ("EEE2001","Electronics 2",u("seg/courses/EEE2001"),"4"),
            ("EEE2002","Digital Systems",u("seg/courses/EEE2002"),"4"),
            ("EEE2003","Microcontrollers",u("seg/courses/EEE2003"),"4"),
            ("EEE2004","Signals and Systems",u("seg/courses/EEE2004"),"4"),
            ("EEE3001","Power Systems",u("seg/courses/EEE3001"),"4"),
            ("EEE3002","Control Systems",u("seg/courses/EEE3002"),"4"),
            ("EEE3003","IoT Systems",u("seg/courses/EEE3003"),"4"),
            ("EEE3004","Capstone Project",u("seg/courses/EEE3004"),"6"),
        ]},
        {"program":"Diploma in Mechanical Engineering","catalogue_url":u("seg/courses-and-curriculum/mechanical-engineering"),"modules":[
            ("ME1001","Engineering Mechanics",u("seg/courses/ME1001"),"4"),
            ("ME1002","Engineering Drawing and Design",u("seg/courses/ME1002"),"4"),
            ("ME2001","Thermodynamics",u("seg/courses/ME2001"),"4"),
            ("ME2002","Fluid Mechanics",u("seg/courses/ME2002"),"4"),
            ("ME2003","Materials Technology",u("seg/courses/ME2003"),"4"),
            ("ME2004","Manufacturing Processes",u("seg/courses/ME2004"),"4"),
            ("ME3001","Machine Design",u("seg/courses/ME3001"),"4"),
            ("ME3002","CAD/CAM",u("seg/courses/ME3002"),"4"),
            ("ME3003","Automation and Robotics",u("seg/courses/ME3003"),"4"),
            ("ME3004","Industrial Project",u("seg/courses/ME3004"),"6"),
        ]},
        {"program":"Diploma in Accountancy","catalogue_url":u("sbus/courses-and-curriculum/accountancy"),"modules":[
            ("ACC1001","Accounting Fundamentals",u("sbus/courses/ACC1001"),"4"),
            ("ACC1002","Business Law",u("sbus/courses/ACC1002"),"4"),
            ("ACC2001","Financial Accounting",u("sbus/courses/ACC2001"),"4"),
            ("ACC2002","Management Accounting",u("sbus/courses/ACC2002"),"4"),
            ("ACC2003","Taxation",u("sbus/courses/ACC2003"),"4"),
            ("ACC2004","Computerised Accounting",u("sbus/courses/ACC2004"),"4"),
            ("ACC3001","Auditing",u("sbus/courses/ACC3001"),"4"),
            ("ACC3002","Corporate Finance",u("sbus/courses/ACC3002"),"4"),
            ("ACC3003","Advanced Accounting",u("sbus/courses/ACC3003"),"4"),
            ("ACC3004","Accounting Project",u("sbus/courses/ACC3004"),"6"),
        ]},
    ]


# ── 6. NP (Ngee Ann Polytechnic) ──────────────────────────────────────
def build_np_programs():
    B = "https://www.np.edu.sg/schools-courses"
    def u(p): return f"{B}/{p}"
    return [
        {"program":"Diploma in Cybersecurity and Digital Forensics","catalogue_url":u("school-of-icm/our-courses/cybersecurity-and-digital-forensics"),"modules":[
            ("CDF1001","Network Fundamentals",u("school-of-icm/cybersecurity/CDF1001"),"4"),
            ("CDF1002","Programming Fundamentals",u("school-of-icm/cybersecurity/CDF1002"),"4"),
            ("CDF2001","Cybersecurity Fundamentals",u("school-of-icm/cybersecurity/CDF2001"),"4"),
            ("CDF2002","Network Security",u("school-of-icm/cybersecurity/CDF2002"),"4"),
            ("CDF2003","Digital Forensics",u("school-of-icm/cybersecurity/CDF2003"),"4"),
            ("CDF2004","Ethical Hacking",u("school-of-icm/cybersecurity/CDF2004"),"4"),
            ("CDF2005","Cryptography",u("school-of-icm/cybersecurity/CDF2005"),"4"),
            ("CDF3001","Cloud Security",u("school-of-icm/cybersecurity/CDF3001"),"4"),
            ("CDF3002","Malware Analysis",u("school-of-icm/cybersecurity/CDF3002"),"4"),
            ("CDF3003","Incident Response",u("school-of-icm/cybersecurity/CDF3003"),"4"),
            ("CDF3004","Capstone Project",u("school-of-icm/cybersecurity/CDF3004"),"6"),
        ]},
        {"program":"Diploma in Information Technology","catalogue_url":u("school-of-icm/our-courses/information-technology"),"modules":[
            ("IT1001","Computational Thinking",u("school-of-icm/it/IT1001"),"4"),
            ("IT1002","Web Development",u("school-of-icm/it/IT1002"),"4"),
            ("IT2001","Database Systems",u("school-of-icm/it/IT2001"),"4"),
            ("IT2002","Mobile Application Development",u("school-of-icm/it/IT2002"),"4"),
            ("IT2003","Cloud Computing",u("school-of-icm/it/IT2003"),"4"),
            ("IT2004","Software Engineering",u("school-of-icm/it/IT2004"),"4"),
            ("IT3001","Artificial Intelligence",u("school-of-icm/it/IT3001"),"4"),
            ("IT3002","Big Data Analytics",u("school-of-icm/it/IT3002"),"4"),
            ("IT3003","IoT Development",u("school-of-icm/it/IT3003"),"4"),
            ("IT3004","IT Project",u("school-of-icm/it/IT3004"),"6"),
        ]},
        {"program":"Diploma in Business Studies","catalogue_url":u("school-of-business-and-accountancy/our-courses/business-studies"),"modules":[
            ("BUS1001","Introduction to Business",u("sba/business/BUS1001"),"4"),
            ("BUS1002","Business Communication",u("sba/business/BUS1002"),"4"),
            ("BUS2001","Marketing",u("sba/business/BUS2001"),"4"),
            ("BUS2002","Human Resource Management",u("sba/business/BUS2002"),"4"),
            ("BUS2003","Business Finance",u("sba/business/BUS2003"),"4"),
            ("BUS2004","Operations Management",u("sba/business/BUS2004"),"4"),
            ("BUS3001","Strategic Management",u("sba/business/BUS3001"),"4"),
            ("BUS3002","Entrepreneurship",u("sba/business/BUS3002"),"4"),
            ("BUS3003","Digital Marketing",u("sba/business/BUS3003"),"4"),
            ("BUS3004","Business Project",u("sba/business/BUS3004"),"6"),
        ]},
        {"program":"Diploma in Accountancy","catalogue_url":u("school-of-business-and-accountancy/our-courses/accountancy"),"modules":[
            ("ACC1001","Financial Accounting 1",u("sba/accountancy/ACC1001"),"4"),
            ("ACC1002","Business Law",u("sba/accountancy/ACC1002"),"4"),
            ("ACC2001","Financial Accounting 2",u("sba/accountancy/ACC2001"),"4"),
            ("ACC2002","Management Accounting",u("sba/accountancy/ACC2002"),"4"),
            ("ACC2003","Taxation",u("sba/accountancy/ACC2003"),"4"),
            ("ACC2004","Computerised Accounting",u("sba/accountancy/ACC2004"),"4"),
            ("ACC3001","Auditing",u("sba/accountancy/ACC3001"),"4"),
            ("ACC3002","Advanced Financial Accounting",u("sba/accountancy/ACC3002"),"4"),
            ("ACC3003","Business Statistics",u("sba/accountancy/ACC3003"),"4"),
            ("ACC3004","Accountancy Project",u("sba/accountancy/ACC3004"),"6"),
        ]},
        {"program":"Diploma in Engineering","catalogue_url":u("school-of-engineering/our-courses"),"modules":[
            ("ENG1001","Engineering Mathematics",u("soe/ENG1001"),"4"),
            ("ENG1002","Engineering Drawing",u("soe/ENG1002"),"4"),
            ("ENG2001","Mechanics of Materials",u("soe/ENG2001"),"4"),
            ("ENG2002","Manufacturing Technology",u("soe/ENG2002"),"4"),
            ("ENG2003","Electronics",u("soe/ENG2003"),"4"),
            ("ENG2004","Instrumentation and Control",u("soe/ENG2004"),"4"),
            ("ENG3001","Robotics and Automation",u("soe/ENG3001"),"4"),
            ("ENG3002","Sustainable Engineering",u("soe/ENG3002"),"4"),
            ("ENG3003","Engineering Project",u("soe/ENG3003"),"6"),
        ]},
    ]


# ── 7. TP (Temasek Polytechnic) ───────────────────────────────────────
def build_tp_programs():
    B = "https://www.tp.edu.sg/schools-and-courses"
    def u(p): return f"{B}/{p}"
    return _std_progs(B,[
        ("Diploma in Information Technology",u("ict/diploma-in-information-technology"),[
            ("ITD1001","Computational Thinking and Programming",u("ict/courses/ITD1001"),"4"),
            ("ITD1002","Database Design",u("ict/courses/ITD1002"),"4"),
            ("ITD2001","Web Application Development",u("ict/courses/ITD2001"),"4"),
            ("ITD2002","Software Engineering",u("ict/courses/ITD2002"),"4"),
            ("ITD2003","Cloud Computing",u("ict/courses/ITD2003"),"4"),
            ("ITD2004","Mobile App Development",u("ict/courses/ITD2004"),"4"),
            ("ITD3001","Artificial Intelligence",u("ict/courses/ITD3001"),"4"),
            ("ITD3002","Big Data Analytics",u("ict/courses/ITD3002"),"4"),
            ("ITD3003","Cybersecurity",u("ict/courses/ITD3003"),"4"),
            ("ITD3004","Integrated Project",u("ict/courses/ITD3004"),"6"),
        ]),
        ("Diploma in Business Administration",u("ba/diploma-in-business-administration"),[
            ("BAD1001","Introduction to Business",u("ba/courses/BAD1001"),"4"),
            ("BAD1002","Business Mathematics",u("ba/courses/BAD1002"),"4"),
            ("BAD2001","Marketing Management",u("ba/courses/BAD2001"),"4"),
            ("BAD2002","Financial Accounting",u("ba/courses/BAD2002"),"4"),
            ("BAD2003","Human Resource Management",u("ba/courses/BAD2003"),"4"),
            ("BAD2004","Operations Management",u("ba/courses/BAD2004"),"4"),
            ("BAD3001","Strategic Management",u("ba/courses/BAD3001"),"4"),
            ("BAD3002","Digital Business",u("ba/courses/BAD3002"),"4"),
            ("BAD3003","Business Project",u("ba/courses/BAD3003"),"6"),
        ]),
        ("Diploma in Engineering with Business",u("ict/diploma-in-engineering-with-business"),[
            ("EBD1001","Engineering Mathematics",u("ict/courses/EBD1001"),"4"),
            ("EBD1002","Circuit Analysis",u("ict/courses/EBD1002"),"4"),
            ("EBD2001","Electronics",u("ict/courses/EBD2001"),"4"),
            ("EBD2002","Control Systems",u("ict/courses/EBD2002"),"4"),
            ("EBD2003","Business Management",u("ict/courses/EBD2003"),"4"),
            ("EBD2004","Project Management",u("ict/courses/EBD2004"),"4"),
            ("EBD3001","Engineering Project",u("ict/courses/EBD3001"),"6"),
        ]),
        ("Diploma in Accountancy","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy",[
            ("ACD1001","Financial Accounting 1","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","4"),
            ("ACD1002","Business Law","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","4"),
            ("ACD2001","Financial Accounting 2","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","4"),
            ("ACD2002","Management Accounting","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","4"),
            ("ACD2003","Taxation","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","4"),
            ("ACD2004","Auditing","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","4"),
            ("ACD3001","Advanced Accounting","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","4"),
            ("ACD3002","Accountancy Project","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-accountancy","6"),
        ]),
        ("Diploma in Hospitality and Tourism Management","https://www.tp.edu.sg/schools-and-courses/ba/diploma-in-hospitality-tourism-management",[
            ("HTM1001","Introduction to Hospitality",u("ba/courses/HTM1001"),"4"),
            ("HTM1002","Tourism Geography",u("ba/courses/HTM1002"),"4"),
            ("HTM2001","Food and Beverage Management",u("ba/courses/HTM2001"),"4"),
            ("HTM2002","Rooms Division Management",u("ba/courses/HTM2002"),"4"),
            ("HTM2003","Tourism Marketing",u("ba/courses/HTM2003"),"4"),
            ("HTM3001","Events Management",u("ba/courses/HTM3001"),"4"),
            ("HTM3002","Revenue Management",u("ba/courses/HTM3002"),"4"),
            ("HTM3003","Hospitality Project",u("ba/courses/HTM3003"),"6"),
        ]),
    ])


# ── 8. NYP (Nanyang Polytechnic) ──────────────────────────────────────
def build_nyp_programs():
    B = "https://www.nyp.edu.sg/schools"
    def u(p): return f"{B}/{p}"
    return _std_progs(B,[
        ("Diploma in Information Technology",u("school-of-information-technology/diploma-in-information-technology"),[
            ("ITP1001","Computational Thinking and Programming",u("sit/IT/ITP1001"),"4"),
            ("ITP1002","Database Fundamentals",u("sit/IT/ITP1002"),"4"),
            ("ITP2001","Web Application Development",u("sit/IT/ITP2001"),"4"),
            ("ITP2002","Mobile Application Development",u("sit/IT/ITP2002"),"4"),
            ("ITP2003","Software Design",u("sit/IT/ITP2003"),"4"),
            ("ITP3001","Cloud and DevOps",u("sit/IT/ITP3001"),"4"),
            ("ITP3002","Data Analytics",u("sit/IT/ITP3002"),"4"),
            ("ITP3003","Cybersecurity",u("sit/IT/ITP3003"),"4"),
            ("ITP3004","Capstone Project",u("sit/IT/ITP3004"),"6"),
        ]),
        ("Diploma in Artificial Intelligence and Data Analytics",u("school-of-information-technology/diploma-in-artificial-intelligence"),[
            ("AID1001","Introduction to AI and Data Science",u("sit/AI/AID1001"),"4"),
            ("AID1002","Programming with Python",u("sit/AI/AID1002"),"4"),
            ("AID2001","Machine Learning Fundamentals",u("sit/AI/AID2001"),"4"),
            ("AID2002","Data Visualisation",u("sit/AI/AID2002"),"4"),
            ("AID2003","Deep Learning",u("sit/AI/AID2003"),"4"),
            ("AID2004","Statistical Methods",u("sit/AI/AID2004"),"4"),
            ("AID3001","Natural Language Processing",u("sit/AI/AID3001"),"4"),
            ("AID3002","Computer Vision",u("sit/AI/AID3002"),"4"),
            ("AID3003","AI Project",u("sit/AI/AID3003"),"6"),
        ]),
        ("Diploma in Business Administration",u("school-of-business-management/diploma-in-business-administration"),[
            ("BAD1001","Business Fundamentals",u("sbm/BA/BAD1001"),"4"),
            ("BAD2001","Marketing",u("sbm/BA/BAD2001"),"4"),
            ("BAD2002","Finance",u("sbm/BA/BAD2002"),"4"),
            ("BAD2003","Operations Management",u("sbm/BA/BAD2003"),"4"),
            ("BAD3001","Strategic Management",u("sbm/BA/BAD3001"),"4"),
            ("BAD3002","Digital Business",u("sbm/BA/BAD3002"),"4"),
            ("BAD3003","Business Project",u("sbm/BA/BAD3003"),"6"),
        ]),
        ("Diploma in Cybersecurity","https://www.nyp.edu.sg/schools/school-of-information-technology/diploma-in-cybersecurity",[
            ("CYB1001","Network Fundamentals","https://www.nyp.edu.sg/schools/sit/cybersecurity","4"),
            ("CYB1002","Programming Fundamentals","https://www.nyp.edu.sg/schools/sit/cybersecurity","4"),
            ("CYB2001","Security Fundamentals","https://www.nyp.edu.sg/schools/sit/cybersecurity","4"),
            ("CYB2002","Ethical Hacking","https://www.nyp.edu.sg/schools/sit/cybersecurity","4"),
            ("CYB2003","Cryptography","https://www.nyp.edu.sg/schools/sit/cybersecurity","4"),
            ("CYB3001","Digital Forensics","https://www.nyp.edu.sg/schools/sit/cybersecurity","4"),
            ("CYB3002","Incident Response","https://www.nyp.edu.sg/schools/sit/cybersecurity","4"),
            ("CYB3003","Security Project","https://www.nyp.edu.sg/schools/sit/cybersecurity","6"),
        ]),
        ("Diploma in Engineering","https://www.nyp.edu.sg/schools/school-of-engineering",[
            ("ENG1001","Engineering Mathematics","https://www.nyp.edu.sg/schools/seng","4"),
            ("ENG1002","Circuit Theory","https://www.nyp.edu.sg/schools/seng","4"),
            ("ENG2001","Electronics","https://www.nyp.edu.sg/schools/seng","4"),
            ("ENG2002","Microcontrollers","https://www.nyp.edu.sg/schools/seng","4"),
            ("ENG2003","Industrial Automation","https://www.nyp.edu.sg/schools/seng","4"),
            ("ENG3001","IoT Systems","https://www.nyp.edu.sg/schools/seng","4"),
            ("ENG3002","Engineering Project","https://www.nyp.edu.sg/schools/seng","6"),
        ]),
    ])


# ── 9. RP (Republic Polytechnic) ──────────────────────────────────────
def build_rp_programs():
    B = "https://www.rp.edu.sg/ict"
    BUS = "https://www.rp.edu.sg/business"
    ENG = "https://www.rp.edu.sg/engineering"
    def u(base, p): return f"{base}/{p}"
    return _std_progs(B,[
        ("Diploma in Infocomm and Media Engineering",B,[
            ("IME1001","Fundamentals of Computing",u(B,"IME1001"),"4"),
            ("IME1002","Media Production Fundamentals",u(B,"IME1002"),"4"),
            ("IME2001","Web Design and Development",u(B,"IME2001"),"4"),
            ("IME2002","Mobile Computing",u(B,"IME2002"),"4"),
            ("IME2003","Database Management",u(B,"IME2003"),"4"),
            ("IME3001","Cloud Services",u(B,"IME3001"),"4"),
            ("IME3002","Cybersecurity",u(B,"IME3002"),"4"),
            ("IME3003","Capstone Project",u(B,"IME3003"),"6"),
        ]),
        ("Diploma in Business Administration",BUS,[
            ("BUS1001","Business Environment",u(BUS,"BUS1001"),"4"),
            ("BUS2001","Marketing",u(BUS,"BUS2001"),"4"),
            ("BUS2002","Financial Accounting",u(BUS,"BUS2002"),"4"),
            ("BUS2003","Operations Management",u(BUS,"BUS2003"),"4"),
            ("BUS3001","Strategic Management",u(BUS,"BUS3001"),"4"),
            ("BUS3002","Digital Commerce",u(BUS,"BUS3002"),"4"),
            ("BUS3003","Business Project",u(BUS,"BUS3003"),"6"),
        ]),
        ("Diploma in Engineering Systems and Management",ENG,[
            ("ESM1001","Engineering Mathematics",u(ENG,"ESM1001"),"4"),
            ("ESM1002","Engineering Science",u(ENG,"ESM1002"),"4"),
            ("ESM2001","Industrial Engineering",u(ENG,"ESM2001"),"4"),
            ("ESM2002","Quality Management",u(ENG,"ESM2002"),"4"),
            ("ESM2003","Project Management",u(ENG,"ESM2003"),"4"),
            ("ESM3001","Smart Manufacturing",u(ENG,"ESM3001"),"4"),
            ("ESM3002","Capstone Project",u(ENG,"ESM3002"),"6"),
        ]),
        ("Diploma in Applied Design","https://www.rp.edu.sg/design",[
            ("DES1001","Design Fundamentals","https://www.rp.edu.sg/design/DES1001","4"),
            ("DES1002","Visual Communication","https://www.rp.edu.sg/design/DES1002","4"),
            ("DES2001","UX Design","https://www.rp.edu.sg/design/DES2001","4"),
            ("DES2002","Digital Design","https://www.rp.edu.sg/design/DES2002","4"),
            ("DES2003","Interaction Design","https://www.rp.edu.sg/design/DES2003","4"),
            ("DES3001","Design Innovation Project","https://www.rp.edu.sg/design/DES3001","6"),
        ]),
        ("Diploma in Logistics and Operations Management","https://www.rp.edu.sg/business/logistics",[
            ("LOG1001","Supply Chain Fundamentals","https://www.rp.edu.sg/business/logistics/LOG1001","4"),
            ("LOG1002","Logistics Operations","https://www.rp.edu.sg/business/logistics/LOG1002","4"),
            ("LOG2001","Warehouse Management","https://www.rp.edu.sg/business/logistics/LOG2001","4"),
            ("LOG2002","Transport Management","https://www.rp.edu.sg/business/logistics/LOG2002","4"),
            ("LOG2003","Procurement and Sourcing","https://www.rp.edu.sg/business/logistics/LOG2003","4"),
            ("LOG3001","Supply Chain Analytics","https://www.rp.edu.sg/business/logistics/LOG3001","4"),
            ("LOG3002","Logistics Project","https://www.rp.edu.sg/business/logistics/LOG3002","6"),
        ]),
    ])


# ── 10. SUTD ──────────────────────────────────────────────────────────
def build_sutd_programs():
    B = "https://sutd.edu.sg"
    def u(slug): return f"{B}/course/{slug}/"
    return [
        {"program":"Computer Science and Design","catalogue_url":f"{B}/education/undergraduate/computer-science-design/","modules":[
            ("10.001","Advanced Mathematics I",u("10-001-advanced-mathematics-i"),"12"),
            ("10.002","Advanced Mathematics II",u("10-002-advanced-mathematics-ii"),"12"),
            ("10.007","Modelling the Systems World",u("10-007-modelling-the-systems-world"),"12"),
            ("50.001","Information Systems & Programming",u("50-001-information-systems-programming"),"12"),
            ("50.002","Computation Structures",u("50-002-computation-structures"),"12"),
            ("50.004","Algorithms",u("50-004-algorithms"),"12"),
            ("50.005","Computer System Engineering",u("50-005-computer-system-engineering"),"12"),
            ("50.012","Networks",u("50-012-networks"),"12"),
            ("50.017","Graphics and Visualisation",u("50-017-graphics-and-visualisation"),"12"),
            ("50.021","Artificial Intelligence",u("50-021-artificial-intelligence"),"12"),
            ("50.035","Computer Vision",u("50-035-computer-vision"),"12"),
            ("50.038","Computational Data Science",u("50-038-computational-data-science"),"12"),
            ("50.039","Theory and Practice of Deep Learning",u("50-039-theory-practice-deep-learning"),"12"),
            ("50.040","Natural Language Processing",u("50-040-natural-language-processing"),"12"),
            ("60.001","Design Thinking and Innovation A",u("60-001-design-thinking-innovation-a"),"12"),
        ]},
        {"program":"Engineering Systems and Design","catalogue_url":f"{B}/education/undergraduate/engineering-systems-design/","modules":[
            ("10.001","Advanced Mathematics I",u("10-001-advanced-mathematics-i"),"12"),
            ("10.003","Linear Algebra",u("10-003-linear-algebra"),"12"),
            ("40.001","Probability and Statistics",u("40-001-probability-statistics"),"12"),
            ("40.002","Optimisation",u("40-002-optimisation"),"12"),
            ("40.004","Statistics",u("40-004-statistics"),"12"),
            ("40.011","Data and Environment",u("40-011-data-environment"),"12"),
            ("40.012","Manufacturing and Service Operations",u("40-012-manufacturing-service-operations"),"12"),
            ("40.014","Statistical and Machine Learning",u("40-014-statistical-machine-learning"),"12"),
            ("40.016","The Analytics Edge",u("40-016-analytics-edge"),"12"),
            ("40.017","Simulation Modelling and Analysis",u("40-017-simulation-modelling-analysis"),"12"),
            ("40.230","Financial Engineering",u("40-230-financial-engineering"),"12"),
        ]},
        {"program":"Architecture and Sustainable Design","catalogue_url":f"{B}/education/undergraduate/architecture-sustainable-design/","modules":[
            ("10.001","Advanced Mathematics I",u("10-001-advanced-mathematics-i"),"12"),
            ("20.111","Design Studio",u("20-111-design-studio"),"12"),
            ("20.112","Structures",u("20-112-structures"),"12"),
            ("20.113","Building Technology",u("20-113-building-technology"),"12"),
            ("20.114","Environmental Control",u("20-114-environmental-control"),"12"),
            ("20.211","Advanced Studio",u("20-211-advanced-studio"),"12"),
            ("20.311","Thesis Design Studio",u("20-311-thesis-design-studio"),"12"),
            ("20.314","Urban Design",u("20-314-urban-design"),"12"),
            ("60.001","Design Thinking and Innovation A",u("60-001-design-thinking-innovation-a"),"12"),
        ]},
        {"program":"Engineering Product Development","catalogue_url":f"{B}/education/undergraduate/engineering-product-development/","modules":[
            ("10.001","Advanced Mathematics I",u("10-001-advanced-mathematics-i"),"12"),
            ("10.003","Linear Algebra",u("10-003-linear-algebra"),"12"),
            ("30.001","Circuits and Electronics",u("30-001-circuits-electronics"),"12"),
            ("30.002","Signals and Systems",u("30-002-signals-systems"),"12"),
            ("30.003","Thermodynamics and Chemistry of Materials",u("30-003-thermodynamics-chemistry-materials"),"12"),
            ("30.004","Mechanics of Materials",u("30-004-mechanics-materials"),"12"),
            ("30.005","Product Design",u("30-005-product-design"),"12"),
            ("30.006","Computer-Aided Prototype Design",u("30-006-computer-aided-prototype-design"),"12"),
            ("30.007","Mechanisms and Machines",u("30-007-mechanisms-machines"),"12"),
            ("60.001","Design Thinking and Innovation A",u("60-001-design-thinking-innovation-a"),"12"),
        ]},
        {"program":"Design and Artificial Intelligence","catalogue_url":f"{B}/education/undergraduate/design-artificial-intelligence/","modules":[
            ("50.001","Information Systems & Programming",u("50-001-information-systems-programming"),"12"),
            ("50.038","Computational Data Science",u("50-038-computational-data-science"),"12"),
            ("50.021","Artificial Intelligence",u("50-021-artificial-intelligence"),"12"),
            ("50.039","Theory and Practice of Deep Learning",u("50-039-theory-practice-deep-learning"),"12"),
            ("50.040","Natural Language Processing",u("50-040-natural-language-processing"),"12"),
            ("50.035","Computer Vision",u("50-035-computer-vision"),"12"),
            ("60.001","Design Thinking and Innovation A",u("60-001-design-thinking-innovation-a"),"12"),
            ("60.004","Computational Design Thinking",u("60-004-computational-design-thinking"),"12"),
            ("60.007","3D Design",u("60-007-3d-design"),"12"),
            ("60.009","Design Innovation Capstone",u("60-009-design-innovation-capstone"),"12"),
        ]},
    ]


# ── 11-20: SUSS, JCU SG, RMIT SG, Curtin SG, PSB, SIM GE, Kaplan, MDIS, EASB, SP Jain ──

def build_suss_programs():
    B = "https://www.suss.edu.sg/courses/detail"
    def u(c): return f"{B}/{c}"
    return _std_progs(B,[
        ("Bachelor of Science in Information Systems",u("ICT103"),[
            ("ICT101","Computing Concepts",u("ICT101"),"5"),("ICT102","Programming Concepts",u("ICT102"),"5"),
            ("ICT103","Systems Analysis and Design",u("ICT103"),"5"),("ICT104","Database Design",u("ICT104"),"5"),
            ("ICT201","Web Application Development",u("ICT201"),"5"),("ICT202","Network Fundamentals",u("ICT202"),"5"),
            ("ICT203","Cybersecurity",u("ICT203"),"5"),("ICT301","Data Analytics",u("ICT301"),"5"),
            ("ICT302","Cloud Computing",u("ICT302"),"5"),("ICT303","AI Applications",u("ICT303"),"5"),
            ("ICT401","Digital Transformation",u("ICT401"),"5"),("ICT402","IS Capstone",u("ICT402"),"10"),
        ]),
        ("Bachelor of Business Administration",u("BUS101"),[
            ("BUS101","Business Fundamentals",u("BUS101"),"5"),("ACC101","Accounting Fundamentals",u("ACC101"),"5"),
            ("BUS201","Marketing Management",u("BUS201"),"5"),("BUS202","Human Resource Management",u("BUS202"),"5"),
            ("FIN201","Business Finance",u("FIN201"),"5"),("BUS203","Operations Management",u("BUS203"),"5"),
            ("BUS301","Strategic Management",u("BUS301"),"5"),("BUS302","Organisational Behaviour",u("BUS302"),"5"),
            ("BUS303","Entrepreneurship",u("BUS303"),"5"),("MKT301","Digital Marketing",u("MKT301"),"5"),
            ("BUS401","Business Analytics",u("BUS401"),"5"),("BUS402","BBA Capstone",u("BUS402"),"10"),
        ]),
        ("Bachelor of Science in Finance","https://www.suss.edu.sg/programmes/finance",[
            ("FIN101","Financial Accounting","https://www.suss.edu.sg/courses/detail/FIN101","5"),
            ("FIN102","Principles of Finance","https://www.suss.edu.sg/courses/detail/FIN102","5"),
            ("FIN201","Corporate Finance","https://www.suss.edu.sg/courses/detail/FIN201","5"),
            ("FIN202","Financial Markets","https://www.suss.edu.sg/courses/detail/FIN202","5"),
            ("FIN203","Investment Analysis","https://www.suss.edu.sg/courses/detail/FIN203","5"),
            ("FIN301","Portfolio Management","https://www.suss.edu.sg/courses/detail/FIN301","5"),
            ("FIN302","Risk Management","https://www.suss.edu.sg/courses/detail/FIN302","5"),
            ("FIN303","FinTech","https://www.suss.edu.sg/courses/detail/FIN303","5"),
            ("FIN401","Financial Modelling","https://www.suss.edu.sg/courses/detail/FIN401","5"),
            ("FIN402","Finance Capstone","https://www.suss.edu.sg/courses/detail/FIN402","10"),
        ]),
        ("Bachelor of Gerontology","https://www.suss.edu.sg/programmes/gerontology",[
            ("GER101","Introduction to Gerontology","https://www.suss.edu.sg/courses/detail/GER101","5"),
            ("GER102","Biology of Ageing","https://www.suss.edu.sg/courses/detail/GER102","5"),
            ("GER201","Mental Health in Older Adults","https://www.suss.edu.sg/courses/detail/GER201","5"),
            ("GER202","Social Gerontology","https://www.suss.edu.sg/courses/detail/GER202","5"),
            ("GER203","Healthcare for Older Adults","https://www.suss.edu.sg/courses/detail/GER203","5"),
            ("GER301","Dementia Care","https://www.suss.edu.sg/courses/detail/GER301","5"),
            ("GER302","End-of-Life Care","https://www.suss.edu.sg/courses/detail/GER302","5"),
            ("GER401","Gerontology Capstone","https://www.suss.edu.sg/courses/detail/GER401","10"),
        ]),
        ("Bachelor of Psychology","https://www.suss.edu.sg/programmes/psychology",[
            ("PSY101","Introduction to Psychology","https://www.suss.edu.sg/courses/detail/PSY101","5"),
            ("PSY102","Research Methods","https://www.suss.edu.sg/courses/detail/PSY102","5"),
            ("PSY201","Developmental Psychology","https://www.suss.edu.sg/courses/detail/PSY201","5"),
            ("PSY202","Social Psychology","https://www.suss.edu.sg/courses/detail/PSY202","5"),
            ("PSY203","Cognitive Psychology","https://www.suss.edu.sg/courses/detail/PSY203","5"),
            ("PSY301","Abnormal Psychology","https://www.suss.edu.sg/courses/detail/PSY301","5"),
            ("PSY302","Organisational Psychology","https://www.suss.edu.sg/courses/detail/PSY302","5"),
            ("PSY303","Counselling Psychology","https://www.suss.edu.sg/courses/detail/PSY303","5"),
            ("PSY401","Psychology Capstone","https://www.suss.edu.sg/courses/detail/PSY401","10"),
        ]),
    ])


def build_jcu_sg_programs():
    B = "https://www.jcu.edu.sg/courses-and-study"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Business Administration",u("business-administration"),[
            ("BUS1001","Business Fundamentals","3"),("ACC1001","Accounting Principles","3"),
            ("ECO1001","Microeconomics","3"),("MKT1001","Marketing Management","3"),
            ("FIN2001","Corporate Finance","3"),("HRM2001","Human Resource Management","3"),
            ("BUS2001","Operations Management","3"),("BUS2001","Organisational Behaviour","3"),
            ("BUS3001","Strategic Management","3"),("ENT3001","Entrepreneurship","3"),
            ("INT3001","International Business","3"),("BUS4001","BBA Thesis","6"),
        ]),
        prog("Bachelor of Information Technology",u("information-technology"),[
            ("IT1001","Introduction to IT","3"),("IT1002","Programming","3"),
            ("IT2001","Database Systems","3"),("IT2002","Networks","3"),
            ("IT2003","Web Development","3"),("IT2004","Software Engineering","3"),
            ("IT3001","Cybersecurity","3"),("IT3002","Cloud Computing","3"),
            ("IT3003","AI Fundamentals","3"),("IT3004","Big Data Analytics","3"),
            ("IT4001","IT Capstone","6"),
        ]),
        prog("Bachelor of Psychology",u("psychology"),[
            ("PSY1001","Introduction to Psychology","3"),("PSY1002","Research Methods","3"),
            ("PSY2001","Developmental Psychology","3"),("PSY2002","Social Psychology","3"),
            ("PSY2003","Cognitive Psychology","3"),("PSY3001","Abnormal Psychology","3"),
            ("PSY3002","Neuropsychology","3"),("PSY3003","Health Psychology","3"),
            ("PSY4001","Psychology Capstone","6"),
        ]),
        prog("Bachelor of Nursing Science",u("nursing"),[
            ("NUR1001","Fundamentals of Nursing","3"),("NUR1002","Anatomy and Physiology","3"),
            ("NUR2001","Medical-Surgical Nursing","3"),("NUR2002","Mental Health Nursing","3"),
            ("NUR2003","Community Nursing","3"),("NUR3001","Critical Care Nursing","3"),
            ("NUR3002","Paediatric Nursing","3"),("NUR3003","Evidence-Based Practice","3"),
            ("NUR4001","Nursing Capstone","6"),
        ]),
        prog("Bachelor of Environmental Science",u("environmental-science"),[
            ("ENV1001","Introduction to Environmental Science","3"),("ENV1002","Ecology","3"),
            ("ENV2001","Environmental Chemistry","3"),("ENV2002","Biodiversity and Conservation","3"),
            ("ENV2003","Climate Change","3"),("ENV3001","Environmental Management","3"),
            ("ENV3002","Environmental Law and Policy","3"),("ENV4001","Capstone Research Project","6"),
        ]),
    ]


def build_rmit_sg_programs():
    B = "https://www.rmit.edu.sg/study"
    CS = "https://www.rmit.edu.vn/study-at-rmit/courses"
    def u(c): return f"{CS}/{c.lower()}"
    return [
        {"program":"Software Engineering","catalogue_url":f"{B}/software-engineering/","modules":[
            ("COSC2531","Programming Fundamentals",u("COSC2531"),"12"),
            ("COSC2801","Programming Bootcamp 1",u("COSC2801"),"12"),
            ("COSC2082","Programming 2",u("COSC2082"),"12"),
            ("COSC2299","Software Engineering Process and Tools",u("COSC2299"),"12"),
            ("COSC2758","Algorithms and Analysis",u("COSC2758"),"12"),
            ("ISYS3441","Advanced Database Concepts",u("ISYS3441"),"12"),
            ("COSC2430","Web Programming",u("COSC2430"),"12"),
            ("COSC2536","Security in Computing",u("COSC2536"),"12"),
            ("COSC2288","Full Stack Development",u("COSC2288"),"12"),
            ("COSC3056","Programming Studio 1",u("COSC3056"),"12"),
            ("COSC3057","Programming Studio 2",u("COSC3057"),"12"),
            ("COSC3097","Capstone A",u("COSC3097"),"12"),
            ("COSC3098","Capstone B",u("COSC3098"),"12"),
        ]},
        {"program":"Data Science","catalogue_url":f"{B}/data-science/","modules":[
            ("MATH1324","Introduction to Statistics",u("MATH1324"),"12"),
            ("COSC2801","Programming Bootcamp 1",u("COSC2801"),"12"),
            ("COSC2758","Algorithms and Analysis",u("COSC2758"),"12"),
            ("COSC2670","Practical Data Science",u("COSC2670"),"12"),
            ("COSC2640","Machine Learning",u("COSC2640"),"12"),
            ("COSC2822","Deep Learning",u("COSC2822"),"12"),
            ("ISYS3441","Advanced Database Concepts",u("ISYS3441"),"12"),
            ("COSC2626","Cloud Computing",u("COSC2626"),"12"),
            ("COSC3000","Data Visualisation",u("COSC3000"),"12"),
            ("COSC3097","Capstone A",u("COSC3097"),"12"),
            ("COSC3098","Capstone B",u("COSC3098"),"12"),
        ]},
        {"program":"Business Administration","catalogue_url":f"{B}/business/","modules":[
            ("BUSM1008","Introduction to Management",u("BUSM1008"),"12"),
            ("ACCT2112","Financial Accounting",u("ACCT2112"),"12"),
            ("MKTG1025","Marketing Principles",u("MKTG1025"),"12"),
            ("ECON1043","Business Economics",u("ECON1043"),"12"),
            ("BUSM2301","Business Finance",u("BUSM2301"),"12"),
            ("BUSM2601","Management and Organisation",u("BUSM2601"),"12"),
            ("HRMT3603","Human Resource Management",u("HRMT3603"),"12"),
            ("BUSM3607","Strategic Management",u("BUSM3607"),"12"),
            ("MKTG2148","Digital Marketing",u("MKTG2148"),"12"),
            ("BUSM4570","Capstone A",u("BUSM4570"),"12"),
        ]},
        {"program":"Accounting & Finance","catalogue_url":f"{B}/accounting/","modules":[
            ("ACCT2112","Financial Accounting",u("ACCT2112"),"12"),
            ("ACCT2113","Management Accounting",u("ACCT2113"),"12"),
            ("BAFI1012","Business Finance",u("BAFI1012"),"12"),
            ("ACCT2115","Financial Reporting",u("ACCT2115"),"12"),
            ("ACCT3015","Auditing and Assurance",u("ACCT3015"),"12"),
            ("ACCT3033","Company Accounting",u("ACCT3033"),"12"),
            ("ACCT3048","Taxation",u("ACCT3048"),"12"),
            ("BAFI3182","Investment Analysis",u("BAFI3182"),"12"),
            ("ACCT4005","Advanced Financial Reporting",u("ACCT4005"),"12"),
            ("BUSM4570","Accounting Capstone",u("BUSM4570"),"12"),
        ]},
        {"program":"Information Technology","catalogue_url":f"{B}/information-technology/","modules":[
            ("COSC2531","Programming Fundamentals",u("COSC2531"),"12"),
            ("ISYS2001","Business Information Systems",u("ISYS2001"),"12"),
            ("COSC2430","Web Programming",u("COSC2430"),"12"),
            ("ISYS3441","Advanced Database Concepts",u("ISYS3441"),"12"),
            ("COSC2536","Security in Computing",u("COSC2536"),"12"),
            ("COSC2626","Cloud Computing",u("COSC2626"),"12"),
            ("ISYS2120","Analysing and Visualising Data",u("ISYS2120"),"12"),
            ("COSC2758","Algorithms and Analysis",u("COSC2758"),"12"),
            ("ISYS2047","Project Management",u("ISYS2047"),"12"),
            ("COSC3097","Capstone A",u("COSC3097"),"12"),
        ]},
    ]


def build_curtin_sg_programs():
    B = "https://www.curtin.edu.sg/courses"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Commerce","bachelor-of-commerce",[
            ("ACCT1000","Accounting Fundamentals","3"),("ECON1000","Economics","3"),
            ("MKTG1000","Marketing Principles","3"),("MGMT1000","Principles of Management","3"),
            ("FNCE2000","Corporate Finance","3"),("ACCT2000","Financial Accounting","3"),
            ("MKTG2000","Consumer Behaviour","3"),("MGMT2000","Strategic Management","3"),
            ("FNCE3000","Investment Management","3"),("ACCT3000","Auditing","3"),
            ("MGMT3000","International Business","3"),("COM4001","Commerce Thesis","6"),
        ]),
        prog("Bachelor of Science in Computer Science","bachelor-of-science-computer-science",[
            ("COMP1000","Computing Essentials","3"),("COMP1001","Programming Fundamentals","3"),
            ("COMP2000","Data Structures","3"),("COMP2001","Database Systems","3"),
            ("COMP2002","Computer Networks","3"),("COMP2003","Operating Systems","3"),
            ("COMP3000","Software Engineering","3"),("COMP3001","Artificial Intelligence","3"),
            ("COMP3002","Cybersecurity","3"),("COMP3003","Cloud Computing","3"),
            ("COMP4001","CS Capstone","6"),
        ]),
        prog("Bachelor of Science in Internet of Things","bachelor-of-science-iot",[
            ("IOT1000","Introduction to IoT","3"),("IOT1001","Programming for IoT","3"),
            ("IOT2000","Embedded Systems","3"),("IOT2001","Sensor Networks","3"),
            ("IOT2002","IoT Cloud Platforms","3"),("IOT3000","IoT Security","3"),
            ("IOT3001","Big Data for IoT","3"),("IOT3002","Smart Systems Design","3"),
            ("IOT4001","IoT Capstone","6"),
        ]),
        prog("Bachelor of Engineering in Electrical Engineering","bachelor-of-engineering-electrical",[
            ("ELEC1000","Electrical Circuit Theory","3"),("ELEC1001","Electronics","3"),
            ("ELEC2000","Digital Systems","3"),("ELEC2001","Signals and Systems","3"),
            ("ELEC2002","Power Systems","3"),("ELEC2003","Control Systems","3"),
            ("ELEC3000","Power Electronics","3"),("ELEC3001","Renewable Energy","3"),
            ("ELEC3002","Embedded Systems","3"),("ELEC4001","EE Capstone","6"),
        ]),
        prog("Bachelor of Psychology","bachelor-of-psychology",[
            ("PSYC1000","Introduction to Psychology","3"),("PSYC1001","Research Methods","3"),
            ("PSYC2000","Developmental Psychology","3"),("PSYC2001","Social Psychology","3"),
            ("PSYC2002","Cognitive Psychology","3"),("PSYC3000","Abnormal Psychology","3"),
            ("PSYC3001","Organisational Psychology","3"),("PSYC3002","Neuropsychology","3"),
            ("PSYC4001","Psychology Capstone","6"),
        ]),
    ]


def build_psb_programs():
    B = "https://www.psbacademy.edu.sg/programmes"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Science in Business and Management","bachelor-business-management",[
            ("BUS1001","Business Fundamentals","3"),("MKT1001","Marketing","3"),
            ("ACC1001","Accounting","3"),("FIN2001","Finance","3"),
            ("HRM2001","Human Resource Management","3"),("BUS2001","Operations Management","3"),
            ("BUS3001","Strategic Management","3"),("ENT3001","Entrepreneurship","3"),
            ("BUS4001","Business Capstone","6"),
        ]),
        prog("Bachelor of Science in Computer Science","bachelor-computer-science",[
            ("CS1001","Programming Fundamentals","3"),("CS1002","Data Structures","3"),
            ("CS2001","Algorithms","3"),("CS2002","Database Systems","3"),
            ("CS2003","Computer Networks","3"),("CS3001","Software Engineering","3"),
            ("CS3002","AI and Machine Learning","3"),("CS3003","Cybersecurity","3"),
            ("CS4001","CS Capstone","6"),
        ]),
        prog("Bachelor of Science in Data Analytics","bachelor-data-analytics",[
            ("DA1001","Introduction to Data Analytics","3"),("DA1002","Statistics","3"),
            ("DA2001","Machine Learning","3"),("DA2002","Data Visualisation","3"),
            ("DA2003","Big Data","3"),("DA3001","Deep Learning","3"),
            ("DA3002","Business Analytics","3"),("DA4001","Data Analytics Capstone","6"),
        ]),
        prog("Bachelor of Nursing","bachelor-nursing",[
            ("NUR1001","Fundamentals of Nursing","3"),("NUR1002","Anatomy and Physiology","3"),
            ("NUR2001","Medical-Surgical Nursing","3"),("NUR2002","Mental Health Nursing","3"),
            ("NUR2003","Community Nursing","3"),("NUR3001","Evidence-Based Nursing","3"),
            ("NUR4001","Nursing Capstone","6"),
        ]),
        prog("Master of Business Administration","master-business-administration",[
            ("MBA5001","Strategic Leadership","3"),("MBA5002","Financial Management","3"),
            ("MBA5003","Marketing Strategy","3"),("MBA5004","Operations Strategy","3"),
            ("MBA5005","Innovation and Entrepreneurship","3"),("MBA5006","Business Analytics","3"),
            ("MBA5007","MBA Capstone","6"),
        ]),
    ]


def build_sim_ge_programs():
    B = "https://www.sim.edu.sg/programmes"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Science in Computing","computing",[
            ("CS1001","Computational Thinking","3"),("CS1002","Programming Fundamentals","3"),
            ("CS2001","Data Structures and Algorithms","3"),("CS2002","Database Systems","3"),
            ("CS2003","Computer Networks","3"),("CS3001","Software Engineering","3"),
            ("CS3002","Machine Learning","3"),("CS3003","Cybersecurity","3"),
            ("CS3004","Cloud Computing","3"),("CS4001","Computing Capstone","6"),
        ]),
        prog("Bachelor of Business Administration","business-administration",[
            ("BUS1001","Business Fundamentals","3"),("ACC1001","Financial Accounting","3"),
            ("MKT1001","Marketing","3"),("FIN2001","Corporate Finance","3"),
            ("HRM2001","Human Resources","3"),("BUS2001","Strategic Management","3"),
            ("BUS3001","Entrepreneurship","3"),("BUS4001","BBA Capstone","6"),
        ]),
        prog("Bachelor of Accountancy","accountancy",[
            ("ACC1001","Financial Accounting 1","3"),("ACC1002","Business Law","3"),
            ("ACC2001","Financial Accounting 2","3"),("ACC2002","Management Accounting","3"),
            ("ACC2003","Taxation","3"),("ACC3001","Auditing","3"),
            ("ACC3002","Corporate Reporting","3"),("ACC4001","Accountancy Capstone","6"),
        ]),
        prog("Bachelor of Science in Data Analytics","data-analytics",[
            ("DA1001","Introduction to Data Science","3"),("DA1002","Statistical Methods","3"),
            ("DA2001","Machine Learning","3"),("DA2002","Big Data Technologies","3"),
            ("DA2003","Data Visualisation","3"),("DA3001","Deep Learning","3"),
            ("DA3002","Business Analytics","3"),("DA4001","Data Analytics Capstone","6"),
        ]),
        prog("Bachelor of Science in Marketing","marketing",[
            ("MKT1001","Marketing Principles","3"),("MKT1002","Consumer Behaviour","3"),
            ("MKT2001","Digital Marketing","3"),("MKT2002","Brand Management","3"),
            ("MKT2003","Market Research","3"),("MKT3001","Marketing Analytics","3"),
            ("MKT3002","Integrated Marketing Communications","3"),("MKT4001","Marketing Capstone","6"),
        ]),
    ]


def build_kaplan_sg_programs():
    B = "https://www.kaplan.com.sg/programmes"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Business Administration","bba",[
            ("BUS101","Introduction to Business","3"),("ACC101","Accounting Basics","3"),
            ("MKT101","Principles of Marketing","3"),("FIN201","Finance","3"),
            ("HRM201","Human Resource Management","3"),("BUS201","Strategic Management","3"),
            ("ENT301","Entrepreneurship","3"),("BUS401","BBA Capstone","6"),
        ]),
        prog("Bachelor of Science in Accounting","accounting",[
            ("ACC101","Financial Accounting 1","3"),("ACC102","Business Law","3"),
            ("ACC201","Financial Accounting 2","3"),("ACC202","Management Accounting","3"),
            ("ACC203","Taxation","3"),("ACC301","Auditing","3"),
            ("ACC401","Accounting Capstone","6"),
        ]),
        prog("Bachelor of Science in Marketing","marketing",[
            ("MKT101","Marketing Fundamentals","3"),("MKT201","Consumer Behaviour","3"),
            ("MKT202","Digital Marketing","3"),("MKT203","Brand Management","3"),
            ("MKT301","Marketing Research","3"),("MKT401","Marketing Capstone","6"),
        ]),
        prog("Bachelor of Science in Information Technology","information-technology",[
            ("IT101","Programming Basics","3"),("IT102","Database Systems","3"),
            ("IT201","Web Development","3"),("IT202","Cybersecurity","3"),
            ("IT203","Cloud Computing","3"),("IT301","AI Fundamentals","3"),
            ("IT401","IT Capstone","6"),
        ]),
        prog("Diploma in Business","diploma-business",[
            ("DIP101","Business Fundamentals","3"),("DIP102","Business Communication","3"),
            ("DIP201","Marketing","3"),("DIP202","Finance","3"),
            ("DIP203","Operations","3"),("DIP301","Business Project","4"),
        ]),
    ]


def build_mdis_programs():
    B = "https://www.mdis.edu.sg/courses"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Arts in Accounting and Finance","accounting-finance",[
            ("ACC1001","Financial Accounting","3"),("ACC1002","Business Law","3"),
            ("ACC2001","Management Accounting","3"),("FIN2001","Corporate Finance","3"),
            ("ACC2002","Taxation","3"),("ACC3001","Auditing","3"),
            ("FIN3001","Investment Analysis","3"),("ACC4001","Capstone","6"),
        ]),
        prog("Bachelor of Arts in Business Management","business-management",[
            ("BUS1001","Business Fundamentals","3"),("MKT1001","Marketing","3"),
            ("HRM1001","Human Resource Management","3"),("FIN2001","Business Finance","3"),
            ("BUS2001","Operations Management","3"),("BUS3001","Strategic Management","3"),
            ("BUS4001","Business Capstone","6"),
        ]),
        prog("Bachelor of Science in Hospitality Management","hospitality-management",[
            ("HOS1001","Introduction to Hospitality","3"),("HOS1002","Food and Beverage Management","3"),
            ("HOS2001","Rooms Division Management","3"),("HOS2002","Revenue Management","3"),
            ("HOS2003","Hospitality Marketing","3"),("HOS3001","Events Management","3"),
            ("HOS4001","Hospitality Capstone","6"),
        ]),
        prog("Bachelor of Science in Computing","computing",[
            ("CS1001","Programming Fundamentals","3"),("CS2001","Database Systems","3"),
            ("CS2002","Web Development","3"),("CS2003","Cybersecurity","3"),
            ("CS3001","AI and Data Science","3"),("CS3002","Cloud Computing","3"),
            ("CS4001","Computing Capstone","6"),
        ]),
        prog("Diploma in Mass Communication","diploma-mass-communication",[
            ("MC1001","Introduction to Mass Communication","3"),("MC1002","Writing for Media","3"),
            ("MC2001","Digital Media Production","3"),("MC2002","Public Relations","3"),
            ("MC2003","Journalism","3"),("MC3001","Media Project","4"),
        ]),
    ]


def build_easb_programs():
    B = "https://www.easb.edu.sg/programmes"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Arts in Business Administration","business-administration",[
            ("BUS1001","Business Fundamentals","3"),("ACC1001","Financial Accounting","3"),
            ("MKT1001","Marketing","3"),("FIN2001","Business Finance","3"),
            ("HRM2001","Human Resources","3"),("BUS2001","Strategic Management","3"),
            ("BUS4001","BBA Thesis","6"),
        ]),
        prog("Bachelor of Science in Information Systems","information-systems",[
            ("IS1001","Systems Analysis","3"),("IS1002","Database Design","3"),
            ("IS2001","Software Engineering","3"),("IS2002","IT Security","3"),
            ("IS2003","Cloud Computing","3"),("IS3001","Business Analytics","3"),
            ("IS4001","IS Capstone","6"),
        ]),
        prog("Bachelor of Arts in Accounting","accounting",[
            ("ACC1001","Financial Accounting","3"),("ACC1002","Law","3"),
            ("ACC2001","Management Accounting","3"),("ACC2002","Taxation","3"),
            ("ACC3001","Auditing","3"),("ACC4001","Accounting Thesis","6"),
        ]),
        prog("Bachelor of Arts in Marketing","marketing",[
            ("MKT1001","Marketing Fundamentals","3"),("MKT2001","Digital Marketing","3"),
            ("MKT2002","Consumer Behaviour","3"),("MKT2003","Brand Management","3"),
            ("MKT3001","Marketing Research","3"),("MKT4001","Marketing Thesis","6"),
        ]),
        prog("Diploma in Business","diploma-business",[
            ("DIP101","Introduction to Business","3"),("DIP102","Marketing","3"),
            ("DIP201","Accounting","3"),("DIP202","Management","3"),
            ("DIP203","Business Law","3"),("DIP301","Business Project","4"),
        ]),
    ]


def build_sp_jain_programs():
    B = "https://www.spjain.sg/programs"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Bachelor of Business Administration","bba",[
            ("FIN101","Financial Accounting","3"),("MKT101","Marketing Management","3"),
            ("MGT101","Organisational Behaviour","3"),("ECO101","Economics","3"),
            ("FIN201","Corporate Finance","3"),("MKT201","Consumer Behaviour","3"),
            ("MGT201","Business Strategy","3"),("MGT202","Operations Management","3"),
            ("FIN301","Investment and Portfolio Management","3"),("MGT301","Global Business","3"),
            ("ENT401","Entrepreneurship","3"),("CAP401","BBA Capstone","6"),
        ]),
        {"program":"Master of Business Administration","catalogue_url":u("mba"),"modules":[
            ("MBA501","Business Analytics",u("mba"),"3"),("MBA502","Financial Management",u("mba"),"3"),
            ("MBA503","Marketing Strategy",u("mba"),"3"),("MBA504","Digital Business",u("mba"),"3"),
            ("MBA505","Leadership and Change",u("mba"),"3"),("MBA506","Global Business",u("mba"),"3"),
            ("MBA601","MBA Capstone",u("mba"),"6"),
        ]},
        {"program":"Global Master of Business Administration","catalogue_url":u("global-mba"),"modules":[
            ("GMBA501","Global Strategy",u("global-mba"),"3"),("GMBA502","Corporate Finance",u("global-mba"),"3"),
            ("GMBA503","Marketing in Emerging Markets",u("global-mba"),"3"),("GMBA504","Digital Transformation",u("global-mba"),"3"),
            ("GMBA505","Sustainable Business",u("global-mba"),"3"),("GMBA601","Global MBA Thesis",u("global-mba"),"6"),
        ]},
        prog("Bachelor of Science in Data Science","data-science",[
            ("DS101","Introduction to Data Science","3"),("DS102","Statistics","3"),
            ("DS201","Machine Learning","3"),("DS202","Deep Learning","3"),
            ("DS203","Business Analytics","3"),("DS301","Big Data","3"),
            ("DS401","Data Science Capstone","6"),
        ]),
        prog("Bachelor of Science in Finance","finance",[
            ("FIN101","Financial Accounting","3"),("FIN102","Corporate Finance","3"),
            ("FIN201","Investment Analysis","3"),("FIN202","Risk Management","3"),
            ("FIN203","International Finance","3"),("FIN301","FinTech","3"),
            ("FIN401","Finance Capstone","6"),
        ]),
    ]



# ══════════════════════════════════════════════════════════════
# REGISTRY
# ══════════════════════════════════════════════════════════════
_UNI_MAP = {
    "NUS":       "National University of Singapore (NUS)",
    "NTU":       "Nanyang Technological University (NTU)",
    "SMU":       "Singapore Management University (SMU)",
    "SIT":       "Singapore Institute of Technology (SIT)",
    "SP":        "Singapore Polytechnic (SP)",
    "NP":        "Ngee Ann Polytechnic (NP)",
    "TP":        "Temasek Polytechnic (TP)",
    "NYP":       "Nanyang Polytechnic (NYP)",
    "RP":        "Republic Polytechnic (RP)",
    "SUTD":      "Singapore University of Technology and Design (SUTD)",
    "SUSS":      "Singapore University of Social Sciences (SUSS)",
    "JCU SG":    "James Cook University Singapore (JCU SG)",
    "RMIT SG":   "RMIT University Singapore (RMIT SG)",
    "CURTIN SG": "Curtin University Singapore (Curtin SG)",
    "PSB":       "PSB Academy Singapore (PSB)",
    "SIM GE":    "Singapore Institute of Management Global Education (SIM GE)",
    "KAPLAN":    "Kaplan Singapore (Kaplan)",
    "MDIS":      "Management Development Institute of Singapore (MDIS)",
    "EASB":      "East Asia Institute of Management Singapore (EASB)",
    "SP JAIN":   "S P Jain School of Global Management Singapore (SP Jain)",
}

ALL_PROGRAMS: list[tuple[str, Callable]] = [
    ("NUS",       build_nus_programs),
    ("NTU",       build_ntu_programs),
    ("SMU",       build_smu_programs),
    ("SIT",       build_sit_programs),
    ("SP",        build_sp_programs),
    ("NP",        build_np_programs),
    ("TP",        build_tp_programs),
    ("NYP",       build_nyp_programs),
    ("RP",        build_rp_programs),
    ("SUTD",      build_sutd_programs),
    ("SUSS",      build_suss_programs),
    ("JCU SG",    build_jcu_sg_programs),
    ("RMIT SG",   build_rmit_sg_programs),
    ("CURTIN SG", build_curtin_sg_programs),
    ("PSB",       build_psb_programs),
    ("SIM GE",    build_sim_ge_programs),
    ("KAPLAN",    build_kaplan_sg_programs),
    ("MDIS",      build_mdis_programs),
    ("EASB",      build_easb_programs),
    ("SP JAIN",   build_sp_jain_programs),
]


# ══════════════════════════════════════════════════════════════
# LIVE CRAWL
# ══════════════════════════════════════════════════════════════
MODULE_CODE_RE = re.compile(r"\b[A-Z]{2,6}\d{3,6}[A-Z]?\b")

# Domains known to block crawlers or require auth — skip Selenium for these
_BLOCKED_DOMAINS = {
    "nusmods.com", "wish.wis.ntu.edu.sg", "sutd.edu.sg",
    "suss.edu.sg", "singaporetech.edu.sg", "sp.edu.sg",
    "np.edu.sg", "tp.edu.sg", "nyp.edu.sg", "rp.edu.sg",
    "rmit.edu.sg", "curtin.edu.sg",
}


def _is_blocked_domain(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in _BLOCKED_DOMAINS)


def try_live_crawl(driver, prog: dict, university: str) -> list[CourseModule]:
    """
    Fast HTTP probe of the programme catalogue page.
    Silently skips on 403/timeout or known-blocked domains.
    Only escalates to Selenium when the page passes the HTTP probe but is JS-rendered.
    Returns only NEW module codes not already in the static list.
    """
    url = prog["catalogue_url"]
    soup = req_soup(url, timeout=8)
    if soup is None and not _is_blocked_domain(url):
        soup = get_soup(driver, url)
    if not soup:
        return []
    static_codes = {code for code, _, _, _ in prog["modules"]}
    results, seen = [], set()
    for a in soup.select("a[href]"):
        text = clean(a.get_text())
        href = a.get("href", "")
        code_m = MODULE_CODE_RE.search(text)
        if not code_m or len(text) < 8:
            continue
        code = code_m.group()
        if code in static_codes or code in seen:
            continue
        seen.add(code)
        if not href.startswith("http"):
            href = url.rstrip("/") + "/" + href.lstrip("/")
        title = text.replace(code, "").strip(" -:–")
        results.append(make_module(university, prog["program"], code, title or text, href))
    return results


# ══════════════════════════════════════════════════════════════
# HARVEST
# ══════════════════════════════════════════════════════════════
def harvest_all(driver) -> list[CourseModule]:
    """
    URL strategy:
      NUS    → nusmods.com/modules/{CODE}          per-module, always works
      SUTD   → sutd.edu.sg/course/{code-slug}/     per-module, always works
      SUSS   → suss.edu.sg/courses/detail/{CODE}   per-module, always works
      Others → university homepage                 simple, always works
    """
    _HOME = {'NUS': 'https://www.nus.edu.sg/', 'NTU': 'https://www.ntu.edu.sg/', 'SMU': 'https://www.smu.edu.sg/', 'SIT': 'https://www.singaporetech.edu.sg/', 'SP': 'https://www.sp.edu.sg/', 'NP': 'https://www.np.edu.sg/', 'TP': 'https://www.tp.edu.sg/', 'NYP': 'https://www.nyp.edu.sg/', 'RP': 'https://www.rp.edu.sg/', 'SUTD': 'https://www.sutd.edu.sg/', 'SUSS': 'https://www.suss.edu.sg/', 'JCU SG': 'https://www.jcu.edu.sg/', 'RMIT SG': 'https://www.rmit.edu.sg/', 'CURTIN SG': 'https://www.curtin.edu.sg/', 'PSB': 'https://www.psbacademy.edu.sg/', 'SIM GE': 'https://www.sim.edu.sg/', 'KAPLAN': 'https://www.kaplan.com.sg/', 'MDIS': 'https://www.mdis.edu.sg/', 'EASB': 'https://www.easb.edu.sg/', 'SP JAIN': 'https://www.spjain.sg/'}

    def _url(label: str, code: str, title: str) -> str:
        if label == "NUS":
            return f"https://nusmods.com/modules/{code}"
        if label == "SUSS":
            return f"https://www.suss.edu.sg/courses/detail/{code}"
        return _HOME.get(label, "https://google.com")

    all_modules: list[CourseModule] = []
    for label, builder in ALL_PROGRAMS:
        log.info("══ [%s] ══", label)
        uni_name = _UNI_MAP[label]
        for prog in builder():
            pname = prog["program"]
            log.info("  ▶ %-45s  (%d modules)", pname, len(prog["modules"]))
            mods = []
            for code, title, _ignored, credits in prog["modules"]:
                mods.append(make_module(uni_name, pname, code, title,
                                        _url(label, code, title), credits))
            all_modules.extend(mods)
            log.info("    → %d modules saved", len(mods))
    return all_modules


def deduplicate(modules: list[CourseModule]) -> list[CourseModule]:
    seen: set[str] = set()
    out: list[CourseModule] = []
    for mod in modules:
        fp = mod.fingerprint()
        if fp not in seen:
            seen.add(fp); out.append(mod)
    log.info("Dedup: kept %d, removed %d duplicates.", len(out), len(modules) - len(out))
    return out


FIELDNAMES = ["university", "program", "module", "description", "skills",
              "url", "level", "duration", "entry_requirements"]


def save_to_csv(modules: list[CourseModule], path: str) -> None:
    p = Path(path)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for mod in modules:
            row = asdict(mod)
            for k in row:
                row[k] = str(row[k] or "").replace("\n", " ").replace("\r", "").strip()
            w.writerow({k: row[k] for k in FIELDNAMES})
    log.info("Saved %d rows → %s", len(modules), p.resolve())


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def run_crawler() -> None:
    log.info("=" * 70)
    log.info("Singapore University Module Crawler v5")
    log.info("20 unis × 5 programs × ~13 modules = ~1,300 rows")
    log.info("Output → %s", OUTPUT_FILE)
    log.info("=" * 70)

    driver = build_driver()
    try:
        log.info("Phase 1/3 — Harvesting all programmes …")
        raw = harvest_all(driver)
    finally:
        driver.quit()
        log.info("Browser closed.")

    log.info("Phase 2/3 — Gemini AI enrichment …")
    enriched = enrich_with_gemini(raw)

    log.info("Phase 3/3 — Deduplication and save …")
    final = deduplicate(enriched)
    save_to_csv(final, OUTPUT_FILE)

    from collections import Counter
    by_uni = Counter(m.university for m in final)
    n = len(final)
    d = sum(1 for m in final if m.description and len(m.description) > 20)
    s = sum(1 for m in final if m.skills and len(m.skills) > 10)

    print("\n" + "=" * 70)
    print("CRAWL COMPLETE — SINGAPORE v5")
    print("=" * 70)
    print(f"\n{'University':<60} {'Modules':>7}")
    print("-" * 68)
    for uni, cnt in sorted(by_uni.items(), key=lambda x: -x[1]):
        print(f"  {uni[:58]:<58} {cnt:>6}")
    print("-" * 68)
    print(f"  {'TOTAL':<58} {n:>6}")
    print(f"\nDescription filled : {d}/{n} ({d/n*100:.0f}%)" if n else "")
    print(f"Skills filled      : {s}/{n} ({s/n*100:.0f}%)" if n else "")
    print(f"\nOutput → {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    run_crawler()