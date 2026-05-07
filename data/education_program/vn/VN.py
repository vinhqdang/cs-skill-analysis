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

OUTPUT_FILE   = "vietnam_modules_v5.csv"
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
log = logging.getLogger("VNv5")
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


_VN_REQ = {
    "Computer Science":       "Khoi A00/A01. DGNL >= 750. IELTS 5.5+ for English-medium.",
    "Software Engineering":   "Khoi A00/A01. IELTS 5.5+.",
    "Information Technology": "Khoi A00/A01. IELTS 5.5+.",
    "Data Science":           "Khoi A00/A01/D07. Strong Mathematics. IELTS 5.5+.",
    "Artificial Intelligence":"Khoi A00/A01. DGNL >= 800. IELTS 5.5+.",
    "Information Security":   "Khoi A00/A01. IELTS 5.5+.",
    "Electrical Engineering": "Khoi A00/A01. Strong Physics.",
    "Electronics":            "Khoi A00/A01. Entrance exam.",
    "Telecommunications":     "Khoi A00/A01. Entrance exam.",
    "Mechanical Engineering": "Khoi A00. Strong Physics and Mathematics.",
    "Civil Engineering":      "Khoi A00. Strong Physics and Mathematics.",
    "Chemical Engineering":   "Khoi A00/B00. Strong Chemistry.",
    "Biomedical Engineering": "Khoi B00/A00. Possible interview.",
    "Materials Engineering":  "Khoi A00/A01. Mathematics and Chemistry.",
    "Mechatronics":           "Khoi A00/A01. Entrance exam.",
    "Business Administration":"Khoi A00/A01/D01. IELTS 5.5+.",
    "Finance":                "Khoi A00/A01/D01. IELTS 5.5+.",
    "Accounting":             "Khoi A00/A01/D01. IELTS 5.5+.",
    "Economics":              "Khoi A00/A01/D01. Quantitative aptitude.",
    "International Business": "Khoi D01 preferred. IELTS 5.5+.",
    "Marketing":              "Khoi D01/A00/A01. IELTS 5.5+.",
    "Law":                    "Khoi C00/D01. IELTS 6.0+.",
    "Tourism Management":     "Khoi D01/A01. IELTS 5.0+.",
    "Logistics":              "Khoi A00/A01/D01. IELTS 5.5+.",
    "Digital Business":       "Khoi A00/A01/D01. IELTS 5.5+.",
    "Finance and Banking":    "Khoi A00/A01/D01. IELTS 5.5+.",
    "Information Systems":    "Khoi A00/A01/D01. IELTS 5.5+.",
    "Environmental Science":  "Khoi B00/A00/D01.",
    "Physics":                "Khoi A00/A01. Excellent Physics.",
    "Biological Sciences":    "Khoi B00. Strong Biology and Chemistry.",
}


def entry_req(program: str, level: str = "Undergraduate") -> str:
    for k, v in _VN_REQ.items():
        if k.lower() in program.lower():
            return v
    if level == "Postgraduate":
        return "Bachelor degree (>=7.0/10). IELTS 6.0+."
    return "THPT graduation. University entrance exam. IELTS 5.5+ for English-taught programmes."


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
# ██  UNIVERSITY PROGRAMME DATA  ██████████████████████████████████████
# ══════════════════════════════════════════════════════════════════════
# Each builder returns a list of 5 dicts:
#   { "program": str,
#     "catalogue_url": str,      ← live programme page to attempt crawl
#     "modules": [(code, title, module_url, credits), ...]  Year 1→4
#   }
# ══════════════════════════════════════════════════════════════════════


# ── 1. VNU-UET ────────────────────────────────────────────────────────
def build_vnu_uet_programs():
    U = "Vietnam National University – University of Engineering and Technology (VNU-UET)"
    C = "https://courses.uet.vnu.edu.vn/course/view.php?id="
    B = "https://uet.vnu.edu.vn/en/academics/undergraduate"
    return [
        {"program":"Computer Science","catalogue_url":f"{B}/computer-science/","modules":[
            ("INT1001","Introduction to Computer Science",f"{C}101","3"),
            ("INT1002","Discrete Mathematics",f"{C}102","3"),
            ("INT1003","Introduction to Programming",f"{C}103","4"),
            ("MAT1001","Calculus 1",f"{C}104","4"),
            ("MAT1002","Linear Algebra",f"{C}105","3"),
            ("INT2201","Data Structures and Algorithms",f"{C}201","4"),
            ("INT2202","Object-Oriented Programming",f"{C}202","3"),
            ("INT2203","Computer Architecture",f"{C}203","3"),
            ("INT2204","Database Systems",f"{C}204","3"),
            ("INT2205","Operating Systems",f"{C}205","3"),
            ("MAT2001","Probability and Statistics",f"{C}206","3"),
            ("INT3101","Computer Networks",f"{C}301","3"),
            ("INT3102","Software Engineering",f"{C}302","3"),
            ("INT3103","Machine Learning",f"{C}303","3"),
            ("INT3104","Artificial Intelligence",f"{C}304","3"),
            ("INT3105","Compiler Design",f"{C}305","3"),
            ("INT3106","Information Security",f"{C}306","3"),
            ("INT4201","Distributed Systems",f"{C}401","3"),
            ("INT4202","Deep Learning",f"{C}402","3"),
            ("INT4203","Natural Language Processing",f"{C}403","3"),
            ("INT4204","Cloud Computing",f"{C}404","3"),
            ("INT4900","Graduation Thesis",f"{C}405","9"),
        ]},
        {"program":"Information Technology","catalogue_url":f"{B}/information-technology/","modules":[
            ("INT1010","Programming Fundamentals",f"{C}110","3"),
            ("INT1011","Digital Logic Design",f"{C}111","3"),
            ("MAT1011","Calculus for IT",f"{C}112","3"),
            ("INT2210","Object-Oriented Design",f"{C}210","3"),
            ("INT2211","Database Management Systems",f"{C}211","3"),
            ("INT2212","Computer Networks Fundamentals",f"{C}212","3"),
            ("INT2213","Web Application Development",f"{C}213","3"),
            ("INT3210","Mobile Application Development",f"{C}310","3"),
            ("INT3211","Information Systems",f"{C}311","3"),
            ("INT3212","Network Security",f"{C}312","3"),
            ("INT3213","Software Testing",f"{C}313","3"),
            ("INT4210","Cloud Services and DevOps",f"{C}410","3"),
            ("INT4211","IT Project Management",f"{C}411","3"),
            ("INT4212","Big Data Analytics",f"{C}412","3"),
            ("INT4910","Capstone IT Project",f"{C}413","9"),
        ]},
        {"program":"Data Science","catalogue_url":f"{B}/data-science/","modules":[
            ("INT1020","Introduction to Data Science",f"{C}120","3"),
            ("MAT1021","Calculus and Linear Algebra",f"{C}121","4"),
            ("MAT1022","Probability and Statistics",f"{C}122","3"),
            ("INT2220","Python for Data Science",f"{C}220","3"),
            ("INT2221","Data Wrangling and Visualisation",f"{C}221","3"),
            ("INT2222","Statistical Learning",f"{C}222","3"),
            ("INT2223","Database Systems for Analytics",f"{C}223","3"),
            ("INT3220","Machine Learning",f"{C}320","3"),
            ("INT3221","Deep Learning",f"{C}321","3"),
            ("INT3222","Big Data Technologies",f"{C}322","3"),
            ("INT3223","Natural Language Processing",f"{C}323","3"),
            ("INT4220","Computer Vision",f"{C}420","3"),
            ("INT4221","Recommender Systems",f"{C}421","3"),
            ("INT4222","MLOps and Model Deployment",f"{C}422","3"),
            ("INT4920","Data Science Capstone",f"{C}423","9"),
        ]},
        {"program":"Information Security","catalogue_url":f"{B}/information-security/","modules":[
            ("INT1030","Introduction to Cybersecurity",f"{C}130","3"),
            ("INT1031","Foundations of Cryptography",f"{C}131","3"),
            ("MAT1031","Discrete Mathematics for Security",f"{C}132","3"),
            ("INT2230","Computer Networks Security",f"{C}230","3"),
            ("INT2231","Operating System Security",f"{C}231","3"),
            ("INT2232","Applied Cryptography",f"{C}232","3"),
            ("INT2233","Secure Programming",f"{C}233","3"),
            ("INT3230","Penetration Testing",f"{C}330","3"),
            ("INT3231","Malware Analysis",f"{C}331","3"),
            ("INT3232","Web Security",f"{C}332","3"),
            ("INT3233","Digital Forensics",f"{C}333","3"),
            ("INT4230","Cloud Security",f"{C}430","3"),
            ("INT4231","IoT Security",f"{C}431","3"),
            ("INT4232","Security Operations and SIEM",f"{C}432","3"),
            ("INT4930","Security Capstone",f"{C}433","9"),
        ]},
        {"program":"Electronics & Telecommunications","catalogue_url":f"{B}/electronics-telecommunications/","modules":[
            ("INT1040","Introduction to Electronics",f"{C}140","3"),
            ("MAT1041","Calculus for Engineering",f"{C}141","4"),
            ("INT1042","Digital Logic Circuits",f"{C}142","3"),
            ("INT2240","Signals and Systems",f"{C}240","3"),
            ("INT2241","Analogue Electronics",f"{C}241","3"),
            ("INT2242","Digital Electronics",f"{C}242","3"),
            ("INT2243","Microprocessors and Microcontrollers",f"{C}243","3"),
            ("INT3240","Communication Systems",f"{C}340","3"),
            ("INT3241","Digital Signal Processing",f"{C}341","3"),
            ("INT3242","Wireless Communications",f"{C}342","3"),
            ("INT3243","Embedded Systems",f"{C}343","3"),
            ("INT4240","4G/5G Mobile Networks",f"{C}440","3"),
            ("INT4241","Internet of Things",f"{C}441","3"),
            ("INT4242","Antenna Design",f"{C}442","3"),
            ("INT4940","Electronics Capstone",f"{C}443","9"),
        ]},
    ]


# ── 2. VNU-UEB ───────────────────────────────────────────────────────
def build_vnu_ueb_programs():
    U = "Vietnam National University Hanoi – University of Economics and Business (VNU-UEB)"
    B = "https://ueb.edu.vn"
    def u(path): return f"{B}/{path}"
    return [
        {"program":"Finance","catalogue_url":u("khoa/tai-chinh-ngan-hang/chuong-trinh-dao-tao/"),"modules":[
            ("FIN1001","Principles of Finance",u("khoa/tai-chinh/fin1001"),"3"),
            ("FIN1002","Financial Accounting",u("khoa/tai-chinh/fin1002"),"3"),
            ("ECO1001","Microeconomics",u("khoa/kinh-te/eco1001"),"3"),
            ("ECO1002","Macroeconomics",u("khoa/kinh-te/eco1002"),"3"),
            ("MATH1001","Mathematics for Economics",u("khoa/toan/math1001"),"3"),
            ("FIN2001","Corporate Finance",u("khoa/tai-chinh/fin2001"),"3"),
            ("FIN2002","Financial Markets and Institutions",u("khoa/tai-chinh/fin2002"),"3"),
            ("FIN2003","Financial Statement Analysis",u("khoa/tai-chinh/fin2003"),"3"),
            ("FIN2004","Money and Banking",u("khoa/tai-chinh/fin2004"),"3"),
            ("STAT2001","Econometrics 1",u("khoa/toan/stat2001"),"3"),
            ("FIN3001","Investment Analysis and Portfolio Management",u("khoa/tai-chinh/fin3001"),"3"),
            ("FIN3002","International Finance",u("khoa/tai-chinh/fin3002"),"3"),
            ("FIN3003","Fixed Income Securities",u("khoa/tai-chinh/fin3003"),"3"),
            ("FIN3004","Derivatives and Risk Management",u("khoa/tai-chinh/fin3004"),"3"),
            ("FIN3005","Public Finance",u("khoa/tai-chinh/fin3005"),"3"),
            ("FIN4001","Mergers and Acquisitions",u("khoa/tai-chinh/fin4001"),"3"),
            ("FIN4002","Financial Modelling",u("khoa/tai-chinh/fin4002"),"3"),
            ("FIN4003","FinTech and Digital Finance",u("khoa/tai-chinh/fin4003"),"3"),
            ("FIN4900","Finance Thesis",u("dao-tao/luan-van"),"9"),
        ]},
        {"program":"Accounting & Finance","catalogue_url":u("khoa/ke-toan-kiem-toan/chuong-trinh-dao-tao/"),"modules":[
            ("ACC1001","Financial Accounting 1",u("khoa/ke-toan/acc1001"),"3"),
            ("ECO1001","Microeconomics",u("khoa/kinh-te/eco1001"),"3"),
            ("MATH1001","Mathematics for Economics",u("khoa/toan/math1001"),"3"),
            ("ACC2001","Financial Accounting 2",u("khoa/ke-toan/acc2001"),"3"),
            ("ACC2002","Managerial Accounting",u("khoa/ke-toan/acc2002"),"3"),
            ("ACC2003","Cost Accounting",u("khoa/ke-toan/acc2003"),"3"),
            ("ACC2004","Tax Accounting",u("khoa/ke-toan/acc2004"),"3"),
            ("ACC2005","Intermediate Financial Accounting",u("khoa/ke-toan/acc2005"),"3"),
            ("ACC3001","Auditing",u("khoa/ke-toan/acc3001"),"3"),
            ("ACC3002","Internal Audit",u("khoa/ke-toan/acc3002"),"3"),
            ("ACC3003","Accounting Information Systems",u("khoa/ke-toan/acc3003"),"3"),
            ("ACC3004","Advanced Financial Accounting",u("khoa/ke-toan/acc3004"),"3"),
            ("ACC4001","International Financial Reporting Standards",u("khoa/ke-toan/acc4001"),"3"),
            ("ACC4002","Forensic Accounting",u("khoa/ke-toan/acc4002"),"3"),
            ("ACC4900","Accounting Thesis",u("dao-tao/luan-van"),"9"),
        ]},
        {"program":"Economics","catalogue_url":u("khoa/kinh-te-chinh-tri/chuong-trinh-dao-tao/"),"modules":[
            ("ECO1001","Microeconomics",u("khoa/kinh-te/eco1001"),"3"),
            ("ECO1002","Macroeconomics",u("khoa/kinh-te/eco1002"),"3"),
            ("MATH1001","Mathematics for Economics",u("khoa/toan/math1001"),"3"),
            ("STAT1001","Statistics",u("khoa/toan/stat1001"),"3"),
            ("ECO2001","Intermediate Microeconomics",u("khoa/kinh-te/eco2001"),"3"),
            ("ECO2002","Intermediate Macroeconomics",u("khoa/kinh-te/eco2002"),"3"),
            ("ECO2003","Development Economics",u("khoa/kinh-te/eco2003"),"3"),
            ("ECO2004","Labour Economics",u("khoa/kinh-te/eco2004"),"3"),
            ("ECO3001","Econometrics 1",u("khoa/kinh-te/eco3001"),"3"),
            ("ECO3002","Econometrics 2",u("khoa/kinh-te/eco3002"),"3"),
            ("ECO3003","Public Economics",u("khoa/kinh-te/eco3003"),"3"),
            ("ECO3004","International Trade Theory",u("khoa/kinh-te/eco3004"),"3"),
            ("ECO4001","Game Theory",u("khoa/kinh-te/eco4001"),"3"),
            ("ECO4002","Environmental Economics",u("khoa/kinh-te/eco4002"),"3"),
            ("ECO4900","Economics Thesis",u("dao-tao/luan-van"),"9"),
        ]},
        {"program":"Business Administration","catalogue_url":u("khoa/quan-tri-kinh-doanh/chuong-trinh-dao-tao/"),"modules":[
            ("MGT1001","Principles of Management",u("khoa/qtqd/mgt1001"),"3"),
            ("ECO1001","Microeconomics",u("khoa/kinh-te/eco1001"),"3"),
            ("ACC1001","Financial Accounting",u("khoa/ke-toan/acc1001"),"3"),
            ("MGT2001","Organisational Behaviour",u("khoa/qtqd/mgt2001"),"3"),
            ("MKT2001","Marketing Management",u("khoa/qtqd/mkt2001"),"3"),
            ("FIN2001","Corporate Finance",u("khoa/tai-chinh/fin2001"),"3"),
            ("MGT2002","Operations Management",u("khoa/qtqd/mgt2002"),"3"),
            ("MGT2003","Human Resource Management",u("khoa/qtqd/mgt2003"),"3"),
            ("SCM3001","Supply Chain Management",u("khoa/qtqd/scm3001"),"3"),
            ("MGT3001","Strategic Management",u("khoa/qtqd/mgt3001"),"3"),
            ("MGT3002","Project Management",u("khoa/qtqd/mgt3002"),"3"),
            ("ENT3001","Entrepreneurship",u("khoa/qtqd/ent3001"),"3"),
            ("MKT3001","Digital Marketing",u("khoa/qtqd/mkt3001"),"3"),
            ("MGT4001","Corporate Governance",u("khoa/qtqd/mgt4001"),"3"),
            ("MGT4900","Business Administration Thesis",u("dao-tao/luan-van"),"9"),
        ]},
        {"program":"International Business","catalogue_url":u("khoa/kinh-te-quoc-te/chuong-trinh-dao-tao/"),"modules":[
            ("INT1001","Introduction to International Business",u("khoa/ktqt/int1001"),"3"),
            ("ECO1001","Microeconomics",u("khoa/kinh-te/eco1001"),"3"),
            ("LAW1001","International Commercial Law",u("khoa/ktqt/law1001"),"3"),
            ("LAN1001","Business English",u("khoa/ktqt/lan1001"),"3"),
            ("INT2001","International Trade Policy",u("khoa/ktqt/int2001"),"3"),
            ("INT2002","Cross-Cultural Management",u("khoa/ktqt/int2002"),"3"),
            ("INT2003","Export-Import Procedures",u("khoa/ktqt/int2003"),"3"),
            ("FIN2001","International Finance",u("khoa/tai-chinh/fin2001"),"3"),
            ("LOG2001","Logistics and Supply Chain",u("khoa/ktqt/log2001"),"3"),
            ("INT3001","WTO Law and Agreements",u("khoa/ktqt/int3001"),"3"),
            ("INT3002","Foreign Direct Investment",u("khoa/ktqt/int3002"),"3"),
            ("INT3003","International Marketing",u("khoa/ktqt/int3003"),"3"),
            ("INT3004","Global Value Chains",u("khoa/ktqt/int3004"),"3"),
            ("INT4001","International Business Strategy",u("khoa/ktqt/int4001"),"3"),
            ("INT4900","International Business Thesis",u("dao-tao/luan-van"),"9"),
        ]},
    ]


# ── 3. HUST ───────────────────────────────────────────────────────────
def build_hust_programs():
    U = "Hanoi University of Science and Technology (HUST)"
    M = "https://soict.daotao.ai/courses/"
    S = "https://soict.hust.edu.vn/en/education/undergraduate-programs/"
    return [
        {"program":"Computer Science","catalogue_url":S,"modules":[
            ("IT3040","Introduction to Computer Science",f"{M}IT3040","3"),
            ("IT3070","Data Structures and Algorithms",f"{M}IT3070","4"),
            ("IT3080","Database Management Systems",f"{M}IT3080","3"),
            ("IT3090","Computer Networks",f"{M}IT3090","3"),
            ("IT3100","Computer Architecture",f"{M}IT3100","3"),
            ("MI1010","Calculus 1",f"{M}MI1010","4"),
            ("MI1020","Probability and Statistics",f"{M}MI1020","3"),
            ("IT3052","Discrete Mathematics",f"{M}IT3052","3"),
            ("IT3180","Operating Systems",f"{M}IT3180","3"),
            ("IT4040","Machine Learning",f"{M}IT4040","3"),
            ("IT3190","Artificial Intelligence",f"{M}IT3190","3"),
            ("IT4409","Web Application Technologies",f"{M}IT4409","3"),
            ("IT4484","Information Security",f"{M}IT4484","3"),
            ("IT3120","Compiler Design",f"{M}IT3120","3"),
            ("IT4483","Cloud Computing and Services",f"{M}IT4483","3"),
            ("IT4020","Deep Learning",f"{M}IT4020","3"),
            ("IT4062","Natural Language Processing",f"{M}IT4062","3"),
            ("IT4901","Senior Thesis",S,"9"),
        ]},
        {"program":"Data Science & Artificial Intelligence","catalogue_url":f"{S}ds-ai/","modules":[
            ("IT3070","Data Structures and Algorithms",f"{M}IT3070","4"),
            ("MI1020","Probability and Statistics",f"{M}MI1020","3"),
            ("IT4040","Machine Learning",f"{M}IT4040","3"),
            ("IT4020","Deep Learning",f"{M}IT4020","3"),
            ("IT4062","Natural Language Processing",f"{M}IT4062","3"),
            ("IT4235","Computer Vision",f"{M}IT4235","3"),
            ("IT3080","Database Management Systems",f"{M}IT3080","3"),
            ("IT4863","Information Retrieval",f"{M}IT4863","3"),
            ("IT4429","Big Data",f"{M}IT4429","3"),
            ("IT4501","Recommender Systems",f"{M}IT4501","3"),
            ("IT4735","Reinforcement Learning",f"{M}IT4735","3"),
            ("IT4594","Graph Neural Networks",f"{M}IT4594","3"),
            ("IT4613","Time Series Analysis",f"{M}IT4613","3"),
            ("IT4621","MLOps",f"{M}IT4621","3"),
            ("IT4901","DS/AI Thesis",S,"9"),
        ]},
        {"program":"Software Engineering","catalogue_url":f"{S}software-engineering/","modules":[
            ("IT3040","Introduction to Computer Science",f"{M}IT3040","3"),
            ("IT3070","Data Structures and Algorithms",f"{M}IT3070","4"),
            ("IT3080","Database Management Systems",f"{M}IT3080","3"),
            ("IT3180","Operating Systems",f"{M}IT3180","3"),
            ("IT4409","Web Application Technologies",f"{M}IT4409","3"),
            ("IT4082","Software Engineering",f"{M}IT4082","3"),
            ("IT4025","Object-Oriented Design",f"{M}IT4025","3"),
            ("IT4015","Mobile App Development",f"{M}IT4015","3"),
            ("IT4172","Software Testing",f"{M}IT4172","3"),
            ("IT4023","Software Architecture",f"{M}IT4023","3"),
            ("IT4483","Cloud Computing",f"{M}IT4483","3"),
            ("IT4663","DevOps and CI/CD",f"{M}IT4663","3"),
            ("IT4681","Agile Methods",f"{M}IT4681","3"),
            ("IT4043","UI/UX Design",f"{M}IT4043","3"),
            ("IT4901","Software Engineering Thesis",S,"9"),
        ]},
        {"program":"Electrical Engineering","catalogue_url":"https://seee.hust.edu.vn/en/education/undergraduate/","modules":[
            ("EE3010","Circuit Theory 1","https://seee.hust.edu.vn/en/education/undergraduate/ee3010","3"),
            ("EE3011","Circuit Theory 2","https://seee.hust.edu.vn/en/education/undergraduate/ee3011","3"),
            ("EE3020","Electronics 1","https://seee.hust.edu.vn/en/education/undergraduate/ee3020","3"),
            ("EE3021","Electronics 2","https://seee.hust.edu.vn/en/education/undergraduate/ee3021","3"),
            ("EE3030","Signals and Systems","https://seee.hust.edu.vn/en/education/undergraduate/ee3030","3"),
            ("EE3040","Electromagnetic Fields","https://seee.hust.edu.vn/en/education/undergraduate/ee3040","3"),
            ("EE4010","Power Systems","https://seee.hust.edu.vn/en/education/undergraduate/ee4010","3"),
            ("EE4011","Power Electronics","https://seee.hust.edu.vn/en/education/undergraduate/ee4011","3"),
            ("EE4020","Control Engineering","https://seee.hust.edu.vn/en/education/undergraduate/ee4020","3"),
            ("EE4030","Electric Machines","https://seee.hust.edu.vn/en/education/undergraduate/ee4030","3"),
            ("EE4040","Digital Signal Processing","https://seee.hust.edu.vn/en/education/undergraduate/ee4040","3"),
            ("EE4050","Renewable Energy Systems","https://seee.hust.edu.vn/en/education/undergraduate/ee4050","3"),
            ("EE4060","PLC and Industrial Automation","https://seee.hust.edu.vn/en/education/undergraduate/ee4060","3"),
            ("EE4070","High Voltage Engineering","https://seee.hust.edu.vn/en/education/undergraduate/ee4070","3"),
            ("EE4901","Electrical Engineering Thesis","https://seee.hust.edu.vn/en/education/undergraduate/","9"),
        ]},
        {"program":"Business Administration","catalogue_url":"https://seam.hust.edu.vn/en/academics/","modules":[
            ("EM1010","Principles of Economics","https://seam.hust.edu.vn/en/academics/em1010","3"),
            ("EM1020","Introduction to Management","https://seam.hust.edu.vn/en/academics/em1020","3"),
            ("ACC1010","Financial Accounting","https://seam.hust.edu.vn/en/academics/acc1010","3"),
            ("EM2010","Marketing Management","https://seam.hust.edu.vn/en/academics/em2010","3"),
            ("EM2020","Human Resource Management","https://seam.hust.edu.vn/en/academics/em2020","3"),
            ("EM3110","Financial Management","https://seam.hust.edu.vn/en/academics/em3110","3"),
            ("EM3120","Operations Management","https://seam.hust.edu.vn/en/academics/em3120","3"),
            ("EM3130","Supply Chain Management","https://seam.hust.edu.vn/en/academics/em3130","3"),
            ("EM3140","Entrepreneurship and Innovation","https://seam.hust.edu.vn/en/academics/em3140","3"),
            ("EM4110","Strategic Management","https://seam.hust.edu.vn/en/academics/em4110","3"),
            ("EM4120","Corporate Finance","https://seam.hust.edu.vn/en/academics/em4120","3"),
            ("EM4130","Digital Business","https://seam.hust.edu.vn/en/academics/em4130","3"),
            ("EM4140","Project Management","https://seam.hust.edu.vn/en/academics/em4140","3"),
            ("EM4901","Business Administration Thesis","https://seam.hust.edu.vn/en/academics/","9"),
        ]},
    ]


# ── 4. FPT ───────────────────────────────────────────────────────────
def build_fpt_programs():
    B = "https://daihoc.fpt.edu.vn/en/program-of-study"
    IT = f"{B}/bachelor-of-information-technology/"
    BA = f"{B}/bachelor-of-business-administration/"
    return [
        {"program":"Software Engineering","catalogue_url":IT,"modules":[
            ("PRF192","Programming Fundamentals",IT,"3"),
            ("PRO192","Object-Oriented Programming",IT,"3"),
            ("OSG202","Operating Systems",IT,"3"),
            ("NWC203","Computer Networks",IT,"3"),
            ("DBI202","Introduction to Databases",IT,"3"),
            ("CSD203","Data Structures and Algorithms",IT,"3"),
            ("SWE201c","Introduction to Software Engineering",IT,"3"),
            ("SWT301","Software Testing",IT,"3"),
            ("SWD392","Web Development Frameworks",IT,"3"),
            ("PRN212","Windows Programming",IT,"3"),
            ("MMA301","Mobile Application Development",IT,"3"),
            ("SWT401","Advanced Software Testing",IT,"3"),
            ("PRN301",".NET and C# Advanced",IT,"3"),
            ("SWP391","Software Development Project",IT,"4"),
            ("SWP490","Graduation Thesis",IT,"10"),
        ]},
        {"program":"Artificial Intelligence","catalogue_url":IT,"modules":[
            ("PRF192","Programming Fundamentals",IT,"3"),
            ("MLN111","Machine Learning Fundamentals",IT,"3"),
            ("AIG201c","Artificial Intelligence",IT,"3"),
            ("MLN131","Deep Learning",IT,"3"),
            ("BDI301","Big Data Analytics",IT,"3"),
            ("MAE101","Mathematics for Engineering",IT,"3"),
            ("SSG104","Statistics",IT,"3"),
            ("IOT102","Introduction to IoT",IT,"3"),
            ("NLP301","Natural Language Processing",IT,"3"),
            ("CVS301","Computer Vision",IT,"3"),
            ("RLB301","Reinforcement Learning",IT,"3"),
            ("AIE301","AI in Healthcare",IT,"3"),
            ("MLO301","Machine Learning Operations",IT,"3"),
            ("CAP491","AI Capstone",IT,"10"),
        ]},
        {"program":"Information Security","catalogue_url":IT,"modules":[
            ("PRF192","Programming Fundamentals",IT,"3"),
            ("NWC203","Computer Networks",IT,"3"),
            ("CYB201c","Cybersecurity Fundamentals",IT,"3"),
            ("CYB301","Network Security",IT,"3"),
            ("CYB302","Cryptography",IT,"3"),
            ("CYB303","Ethical Hacking and Penetration Testing",IT,"3"),
            ("CYB304","Digital Forensics",IT,"3"),
            ("CYB305","Secure Software Development",IT,"3"),
            ("CYB306","Web Application Security",IT,"3"),
            ("CYB307","Malware Analysis",IT,"3"),
            ("CYB401","Cloud Security",IT,"3"),
            ("CYB402","Security Operations Centre",IT,"3"),
            ("CYB403","IoT Security",IT,"3"),
            ("CAP492","Security Capstone",IT,"10"),
        ]},
        {"program":"Business Administration","catalogue_url":BA,"modules":[
            ("BAA101","Introduction to Business",BA,"3"),
            ("BAF201","Financial Accounting",BA,"3"),
            ("BAM201","Principles of Management",BA,"3"),
            ("BAK201","Marketing Management",BA,"3"),
            ("BAK301","Digital Marketing",BA,"3"),
            ("BAL201","Business Law",BA,"3"),
            ("BAF301","Corporate Finance",BA,"3"),
            ("BAE201","Microeconomics",BA,"3"),
            ("BAE202","Macroeconomics",BA,"3"),
            ("BAM301","Strategic Management",BA,"3"),
            ("BAM302","Organisational Behaviour",BA,"3"),
            ("BAM303","Human Resource Management",BA,"3"),
            ("BAS301","Supply Chain Management",BA,"3"),
            ("BAT301","Business Analytics",BA,"3"),
            ("BAC490","BBA Thesis",BA,"10"),
        ]},
        {"program":"Digital Marketing","catalogue_url":BA,"modules":[
            ("DMK101","Introduction to Digital Marketing",BA,"3"),
            ("BAK201","Marketing Management",BA,"3"),
            ("DMK201","Social Media Marketing",BA,"3"),
            ("DMK202","Search Engine Optimisation",BA,"3"),
            ("DMK203","Content Marketing",BA,"3"),
            ("DMK204","Email and CRM Marketing",BA,"3"),
            ("DMK205","Programmatic Advertising",BA,"3"),
            ("DMK301","Data Analytics for Marketing",BA,"3"),
            ("DMK302","E-Commerce Management",BA,"3"),
            ("DMK303","Influencer and Affiliate Marketing",BA,"3"),
            ("DMK304","Brand Management",BA,"3"),
            ("DMK401","Marketing Technology Stack",BA,"3"),
            ("DMK402","Consumer Behaviour",BA,"3"),
            ("DMK490","Digital Marketing Thesis",BA,"10"),
        ]},
    ]


# ── 5. RMIT VIETNAM ───────────────────────────────────────────────────
def build_rmit_vn_programs():
    B = "https://www.rmit.edu.vn/study-at-rmit/courses"
    def u(c): return f"{B}/{c.lower()}"
    def P(n,cat,mods): return {"program":n,"catalogue_url":cat,"modules":mods}
    SE  = "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/software-engineering/"
    DS  = "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/data-science/"
    IT  = "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/information-technology/"
    BUS = "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/business/"
    ACC = "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/accounting/"
    return [
        P("Software Engineering",SE,[
            ("COSC2531","Programming Fundamentals",u("COSC2531"),"12"),
            ("COSC2801","Programming Bootcamp 1",u("COSC2801"),"12"),
            ("COSC2082","Programming 2",u("COSC2082"),"12"),
            ("COSC2299","Software Engineering Process and Tools",u("COSC2299"),"12"),
            ("COSC2430","Web Programming",u("COSC2430"),"12"),
            ("COSC2758","Algorithms and Analysis",u("COSC2758"),"12"),
            ("ISYS3441","Advanced Database Concepts",u("ISYS3441"),"12"),
            ("COSC2391","Further Programming",u("COSC2391"),"12"),
            ("COSC2288","Full Stack Development",u("COSC2288"),"12"),
            ("COSC3056","Programming Studio 1",u("COSC3056"),"12"),
            ("COSC3057","Programming Studio 2",u("COSC3057"),"12"),
            ("COSC2536","Security in Computing and IT",u("COSC2536"),"12"),
            ("COSC3060","Professional Practice",u("COSC3060"),"12"),
            ("COSC3097","Capstone Project A",u("COSC3097"),"12"),
            ("COSC3098","Capstone Project B",u("COSC3098"),"12"),
        ]),
        P("Data Science",DS,[
            ("MATH1324","Introduction to Statistics",u("MATH1324"),"12"),
            ("MATH1318","Applied Bayesian Statistics",u("MATH1318"),"12"),
            ("COSC2801","Programming Bootcamp 1",u("COSC2801"),"12"),
            ("COSC2758","Algorithms and Analysis",u("COSC2758"),"12"),
            ("COSC2670","Practical Data Science",u("COSC2670"),"12"),
            ("COSC2640","Machine Learning",u("COSC2640"),"12"),
            ("COSC2822","Deep Learning",u("COSC2822"),"12"),
            ("COSC2927","Natural Language Processing",u("COSC2927"),"12"),
            ("COSC2626","Cloud Computing",u("COSC2626"),"12"),
            ("ISYS3441","Advanced Database Concepts",u("ISYS3441"),"12"),
            ("MATH2200","Computational Mathematics",u("MATH2200"),"12"),
            ("COSC3000","Data Visualisation",u("COSC3000"),"12"),
            ("COSC3097","Capstone Project A",u("COSC3097"),"12"),
            ("COSC3098","Capstone Project B",u("COSC3098"),"12"),
        ]),
        P("Information Technology",IT,[
            ("COSC2531","Programming Fundamentals",u("COSC2531"),"12"),
            ("ISYS2001","Introduction to Business Information Systems",u("ISYS2001"),"12"),
            ("COSC2430","Web Programming",u("COSC2430"),"12"),
            ("ISYS3441","Advanced Database Concepts",u("ISYS3441"),"12"),
            ("COSC2536","Security in Computing and IT",u("COSC2536"),"12"),
            ("COSC2758","Algorithms and Analysis",u("COSC2758"),"12"),
            ("COSC2626","Cloud Computing",u("COSC2626"),"12"),
            ("ISYS2120","Analysing and Visualising Data",u("ISYS2120"),"12"),
            ("ISYS3412","Human-Computer Interaction",u("ISYS3412"),"12"),
            ("COSC2391","Further Programming",u("COSC2391"),"12"),
            ("ISYS2047","Project Management",u("ISYS2047"),"12"),
            ("COSC3056","Programming Studio 1",u("COSC3056"),"12"),
            ("COSC3060","Professional Practice",u("COSC3060"),"12"),
            ("COSC3097","Capstone Project A",u("COSC3097"),"12"),
            ("COSC3098","Capstone Project B",u("COSC3098"),"12"),
        ]),
        P("Business Administration",BUS,[
            ("BUSM1008","Introduction to Management",u("BUSM1008"),"12"),
            ("ACCT2112","Financial Accounting",u("ACCT2112"),"12"),
            ("MKTG1025","Marketing Principles",u("MKTG1025"),"12"),
            ("ECON1043","Business Economics",u("ECON1043"),"12"),
            ("BUSM2301","Business Finance",u("BUSM2301"),"12"),
            ("BUSM2601","Management and Organisation",u("BUSM2601"),"12"),
            ("MKTG2149","Consumer Behaviour",u("MKTG2149"),"12"),
            ("HRMT3603","Human Resource Management",u("HRMT3603"),"12"),
            ("BUSM3200","Entrepreneurship",u("BUSM3200"),"12"),
            ("BUSM3607","Strategic Management",u("BUSM3607"),"12"),
            ("MKTG3491","International Marketing",u("MKTG3491"),"12"),
            ("BUSM3600","Operations Management",u("BUSM3600"),"12"),
            ("MKTG2148","Digital Marketing Strategy",u("MKTG2148"),"12"),
            ("BUSM4570","Business Capstone A",u("BUSM4570"),"12"),
            ("BUSM4571","Business Capstone B",u("BUSM4571"),"12"),
        ]),
        P("Accounting & Finance",ACC,[
            ("ACCT2112","Financial Accounting",u("ACCT2112"),"12"),
            ("ACCT2113","Management Accounting",u("ACCT2113"),"12"),
            ("BAFI1012","Business Finance",u("BAFI1012"),"12"),
            ("ACCT2115","Financial Reporting",u("ACCT2115"),"12"),
            ("ACCT3015","Auditing and Assurance",u("ACCT3015"),"12"),
            ("ACCT3033","Company Accounting",u("ACCT3033"),"12"),
            ("ACCT3048","Taxation",u("ACCT3048"),"12"),
            ("BAFI3182","Investment Analysis",u("BAFI3182"),"12"),
            ("ACCT3016","Accounting Systems and Controls",u("ACCT3016"),"12"),
            ("ACCT4005","Advanced Financial Reporting",u("ACCT4005"),"12"),
            ("BAFI3184","Derivatives and Risk Management",u("BAFI3184"),"12"),
            ("ACCT2114","Cost and Management Accounting",u("ACCT2114"),"12"),
            ("ACCT4080","Research in Accounting",u("ACCT4080"),"12"),
            ("BUSM4570","Accounting Capstone A",u("BUSM4570"),"12"),
            ("BUSM4571","Accounting Capstone B",u("BUSM4571"),"12"),
        ]),
    ]


# ── 6. HCMUT ─────────────────────────────────────────────────────────
def build_hcmut_programs():
    B = "https://hcmut.edu.vn/en/academics/undergraduate"
    return [
        {"program":"Computer Science","catalogue_url":f"{B}/computer-science/","modules":[
            ("CO1005","Introduction to Computing",f"{B}/","3"),("CO1007","Discrete Structures",f"{B}/","3"),
            ("CO1023","Digital Systems",f"{B}/","3"),("CO1027","Programming Techniques",f"{B}/","3"),
            ("MT1003","Calculus",f"{B}/","4"),("CO2003","Data Structures and Algorithms",f"{B}/","3"),
            ("CO2007","Computer Organisation and Architecture",f"{B}/","3"),("CO2013","Database Systems",f"{B}/","3"),
            ("CO2039","Advanced Programming",f"{B}/","3"),("MT2003","Probability and Statistics",f"{B}/","3"),
            ("CO3001","Software Engineering",f"{B}/","3"),("CO3049","Introduction to Machine Learning",f"{B}/","3"),
            ("CO3093","Computer Networks",f"{B}/","3"),("CO3025","Operating Systems",f"{B}/","3"),
            ("CO3117","Artificial Intelligence",f"{B}/","3"),("CO4027","Big Data Systems",f"{B}/","3"),
            ("CO4031","Computer Security",f"{B}/","3"),("CO4029","Computer Vision",f"{B}/","3"),
            ("CO4901","Senior Thesis",f"{B}/","9"),
        ]},
        {"program":"Electrical Engineering","catalogue_url":f"{B}/electrical-engineering/","modules":[
            ("EE1003","Circuit Theory",f"{B}/","3"),("EE1013","Electronics 1",f"{B}/","3"),
            ("MT1003","Calculus",f"{B}/","4"),("PH1003","Physics",f"{B}/","3"),
            ("EE2013","Electronics 2",f"{B}/","3"),("EE2023","Signals and Systems",f"{B}/","3"),
            ("EE2033","Electromagnetic Theory",f"{B}/","3"),("EE3013","Power Systems",f"{B}/","3"),
            ("EE3023","Control Systems",f"{B}/","3"),("EE3033","Power Electronics",f"{B}/","3"),
            ("EE3043","Electric Machines",f"{B}/","3"),("EE4013","Renewable Energy",f"{B}/","3"),
            ("EE4023","Smart Grid",f"{B}/","3"),("EE4033","High Voltage Engineering",f"{B}/","3"),
            ("EE4901","Electrical Engineering Thesis",f"{B}/","9"),
        ]},
        {"program":"Civil Engineering","catalogue_url":f"{B}/civil-engineering/","modules":[
            ("CE1001","Engineering Mechanics",f"{B}/","3"),("CE1002","Engineering Drawing",f"{B}/","3"),
            ("MT1003","Calculus",f"{B}/","4"),("CE2001","Mechanics of Materials",f"{B}/","3"),
            ("CE2002","Structural Analysis",f"{B}/","3"),("CE2003","Soil Mechanics",f"{B}/","3"),
            ("CE2004","Hydraulics",f"{B}/","3"),("CE2005","Surveying",f"{B}/","3"),
            ("CE3001","Foundation Engineering",f"{B}/","3"),("CE3002","Reinforced Concrete Design",f"{B}/","3"),
            ("CE3003","Steel Structure Design",f"{B}/","3"),("CE3004","Road Engineering",f"{B}/","3"),
            ("CE4001","Bridge Engineering",f"{B}/","3"),("CE4002","Construction Management",f"{B}/","3"),
            ("CE4901","Civil Engineering Thesis",f"{B}/","9"),
        ]},
        {"program":"Mechanical Engineering","catalogue_url":f"{B}/mechanical-engineering/","modules":[
            ("ME1001","Engineering Mechanics",f"{B}/","3"),("MT1003","Calculus",f"{B}/","4"),
            ("PH1003","Physics",f"{B}/","3"),("ME2001","Thermodynamics",f"{B}/","3"),
            ("ME2002","Fluid Mechanics",f"{B}/","3"),("ME2003","Mechanics of Materials",f"{B}/","3"),
            ("ME2004","Machine Design",f"{B}/","3"),("ME3001","Manufacturing Technology",f"{B}/","3"),
            ("ME3002","Heat Transfer",f"{B}/","3"),("ME3003","Internal Combustion Engines",f"{B}/","3"),
            ("ME3004","CAD/CAM",f"{B}/","3"),("ME4001","Finite Element Methods",f"{B}/","3"),
            ("ME4002","Mechatronics",f"{B}/","3"),("ME4003","Industrial Automation",f"{B}/","3"),
            ("ME4901","Mechanical Engineering Thesis",f"{B}/","9"),
        ]},
        {"program":"Biomedical Engineering","catalogue_url":f"{B}/biomedical-engineering/","modules":[
            ("BM1001","Introduction to Biomedical Engineering",f"{B}/","3"),
            ("BM1002","Biology for Engineers",f"{B}/","3"),("MT1003","Calculus",f"{B}/","4"),
            ("BM2001","Biomechanics",f"{B}/","3"),("BM2002","Biomedical Signals",f"{B}/","3"),
            ("BM2003","Physiology for Engineers",f"{B}/","3"),("BM2004","Medical Instrumentation",f"{B}/","3"),
            ("BM3001","Medical Imaging",f"{B}/","3"),("BM3002","Biomaterials",f"{B}/","3"),
            ("BM3003","Neural Engineering",f"{B}/","3"),("BM3004","Rehabilitation Engineering",f"{B}/","3"),
            ("BM4001","Medical Device Regulation",f"{B}/","3"),("BM4002","Clinical Engineering",f"{B}/","3"),
            ("BM4003","Tissue Engineering",f"{B}/","3"),("BM4901","Biomedical Engineering Thesis",f"{B}/","9"),
        ]},
    ]


# ── 7-20. Remaining 14 universities ───────────────────────────────────
# (VNU-HCMUS, UEH, TDTU, VGU, BUV, HUTE, HANU, FTU, NEU, UIT, CTU, DUT, PHENIKAA, PTIT)

def _simple_prog(name, cat, base, mods):
    return {"program": name, "catalogue_url": cat, "modules": [
        (c, t, f"{base}/{c.lower()}" if not u.startswith("http") else u, cr)
        for c, t, u, cr in mods
    ]}


def build_hcmus_programs():
    B = "https://www.hcmus.edu.vn/dao-tao/dai-hoc"
    def u(c): return f"{B}/{c.lower()}"
    return [
        {"program":"Computer Science","catalogue_url":f"{B}/khoa-hoc-may-tinh/","modules":[
            ("CSC10001","Introduction to Programming",u("csc10001"),"4"),("CSC10002","Data Structures and Algorithms",u("csc10002"),"4"),
            ("CSC10003","Operating Systems",u("csc10003"),"3"),("CSC10004","Database Systems",u("csc10004"),"3"),
            ("CSC10008","Computer Networks",u("csc10008"),"3"),("MTH00002","Probability and Statistics",u("mth00002"),"3"),
            ("MTH00003","Linear Algebra",u("mth00003"),"3"),("MTH00004","Discrete Mathematics",u("mth00004"),"3"),
            ("CSC10009","Advanced Data Structures",u("csc10009"),"3"),("CSC10006","Algorithm Design",u("csc10006"),"3"),
            ("CSC14005","Machine Learning",u("csc14005"),"3"),("CSC14003","Artificial Intelligence",u("csc14003"),"3"),
            ("CSC00004","Web Programming",u("csc00004"),"3"),("CSC14119","Deep Learning",u("csc14119"),"3"),
            ("CSC14116","Natural Language Processing",u("csc14116"),"3"),("CSC14111","Computer Vision",u("csc14111"),"3"),
            ("CSC13114","Information Security",u("csc13114"),"3"),("CSC14000","Capstone Project",u("csc14000"),"9"),
        ]},
        {"program":"Data Science","catalogue_url":f"{B}/khoa-hoc-du-lieu/","modules":[
            ("DSC10001","Foundations of Data Science",u("dsc10001"),"3"),("CSC10001","Introduction to Programming",u("csc10001"),"4"),
            ("MTH00002","Probability and Statistics",u("mth00002"),"3"),("MTH00003","Linear Algebra",u("mth00003"),"3"),
            ("DSC20001","Statistical Learning",u("dsc20001"),"3"),("DSC20002","Data Wrangling and Visualisation",u("dsc20002"),"3"),
            ("DSC20003","Database for Data Science",u("dsc20003"),"3"),("DSC30001","Applied Machine Learning",u("dsc30001"),"3"),
            ("DSC30002","Time Series Analysis",u("dsc30002"),"3"),("DSC30003","Big Data Technologies",u("dsc30003"),"3"),
            ("DSC30004","Deep Learning",u("dsc30004"),"3"),("DSC30005","NLP for Data Science",u("dsc30005"),"3"),
            ("DSC40001","Data Science Ethics",u("dsc40001"),"3"),("DSC40002","Capstone Data Science Project",u("dsc40002"),"9"),
        ]},
        {"program":"Biological Sciences","catalogue_url":f"{B}/sinh-hoc/","modules":[
            ("BIO10001","Introduction to Biology",u("bio10001"),"3"),("BIO10002","Cell Biology",u("bio10002"),"3"),
            ("BIO10003","Genetics",u("bio10003"),"3"),("BIO20001","Microbiology",u("bio20001"),"3"),
            ("BIO20002","Biochemistry",u("bio20002"),"3"),("BIO20003","Ecology",u("bio20003"),"3"),
            ("BIO20004","Molecular Biology",u("bio20004"),"3"),("BIO30001","Physiology",u("bio30001"),"3"),
            ("BIO30002","Evolution",u("bio30002"),"3"),("BIO30003","Bioinformatics",u("bio30003"),"3"),
            ("BIO30004","Immunology",u("bio30004"),"3"),("BIO40001","Biotechnology",u("bio40001"),"3"),
            ("BIO40002","Environmental Biology",u("bio40002"),"3"),("BIO40003","Senior Biology Thesis",u("bio40003"),"9"),
        ]},
        {"program":"Physics","catalogue_url":f"{B}/vat-ly/","modules":[
            ("PHY10001","Classical Mechanics",u("phy10001"),"4"),("PHY10002","Electricity and Magnetism",u("phy10002"),"4"),
            ("MTH00001","Calculus 1",u("mth00001"),"4"),("PHY20001","Thermodynamics and Statistical Physics",u("phy20001"),"3"),
            ("PHY20002","Quantum Mechanics 1",u("phy20002"),"3"),("PHY20003","Optics",u("phy20003"),"3"),
            ("MTH00002","Probability and Statistics",u("mth00002"),"3"),("PHY30001","Solid State Physics",u("phy30001"),"3"),
            ("PHY30002","Nuclear Physics",u("phy30002"),"3"),("PHY30003","Quantum Mechanics 2",u("phy30003"),"3"),
            ("PHY30004","Computational Physics",u("phy30004"),"3"),("PHY40001","Photonics",u("phy40001"),"3"),
            ("PHY40002","Nanotechnology",u("phy40002"),"3"),("PHY40003","Physics Thesis",u("phy40003"),"9"),
        ]},
        {"program":"Environmental Science","catalogue_url":f"{B}/moi-truong/","modules":[
            ("ENV10001","Introduction to Environmental Science",u("env10001"),"3"),("ENV10002","Ecology",u("env10002"),"3"),
            ("CHE10001","General Chemistry",u("che10001"),"3"),("ENV20001","Environmental Chemistry",u("env20001"),"3"),
            ("ENV20002","Water Resources Management",u("env20002"),"3"),("ENV20003","Air Quality Management",u("env20003"),"3"),
            ("ENV20004","Soil and Land Degradation",u("env20004"),"3"),("ENV30001","Environmental Impact Assessment",u("env30001"),"3"),
            ("ENV30002","Climate Change Science",u("env30002"),"3"),("ENV30003","Waste Management",u("env30003"),"3"),
            ("ENV30004","Remote Sensing and GIS",u("env30004"),"3"),("ENV40001","Environmental Policy",u("env40001"),"3"),
            ("ENV40002","Sustainability Management",u("env40002"),"3"),("ENV40003","Environmental Science Thesis",u("env40003"),"9"),
        ]},
    ]


def build_ueh_programs():
    B = "https://ueh.edu.vn/en/education/training-programs"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":mods}
    return [
        prog("Finance","finance",[
            ("FIN1001","Principles of Finance",u("finance"),"3"),("ACC1001","Financial Accounting",u("finance"),"3"),
            ("ECO1001","Microeconomics",u("finance"),"3"),("ECO1002","Macroeconomics",u("finance"),"3"),
            ("FIN2001","Corporate Finance",u("finance"),"3"),("FIN2002","Financial Markets",u("finance"),"3"),
            ("FIN2003","Money and Banking",u("finance"),"3"),("FIN2004","Financial Statement Analysis",u("finance"),"3"),
            ("FIN3001","Investment Analysis",u("finance"),"3"),("FIN3002","Portfolio Management",u("finance"),"3"),
            ("FIN3003","International Finance",u("finance"),"3"),("FIN3004","Fixed Income Securities",u("finance"),"3"),
            ("FIN3005","Derivatives",u("finance"),"3"),("FIN4001","Financial Risk Management",u("finance"),"3"),
            ("FIN4002","FinTech and Digital Finance",u("finance"),"3"),("FIN4003","Financial Modelling",u("finance"),"3"),
            ("FIN4900","Finance Thesis",u("finance"),"9"),
        ]),
        prog("Accounting","accounting",[
            ("ACC1001","Financial Accounting",u("accounting"),"3"),("ECO1001","Microeconomics",u("accounting"),"3"),
            ("ACC2001","Intermediate Accounting",u("accounting"),"3"),("ACC2002","Managerial Accounting",u("accounting"),"3"),
            ("ACC2003","Cost Accounting",u("accounting"),"3"),("ACC2004","Tax Accounting",u("accounting"),"3"),
            ("ACC3001","Auditing",u("accounting"),"3"),("ACC3002","Advanced Financial Accounting",u("accounting"),"3"),
            ("ACC3003","Accounting Information Systems",u("accounting"),"3"),("ACC3004","Internal Control",u("accounting"),"3"),
            ("ACC4001","IFRS and International Accounting",u("accounting"),"3"),("ACC4002","Forensic Accounting",u("accounting"),"3"),
            ("ACC4003","Government Accounting",u("accounting"),"3"),("ACC4900","Accounting Thesis",u("accounting"),"9"),
        ]),
        prog("Business Administration","business-administration",[
            ("MGT1001","Principles of Management",u("business-administration"),"3"),
            ("MKT1001","Marketing Principles",u("business-administration"),"3"),
            ("ACC1001","Financial Accounting",u("business-administration"),"3"),
            ("ECO1001","Microeconomics",u("business-administration"),"3"),
            ("MGT2001","Organisational Behaviour",u("business-administration"),"3"),
            ("MGT2002","Human Resource Management",u("business-administration"),"3"),
            ("MGT2003","Operations Management",u("business-administration"),"3"),
            ("FIN2001","Corporate Finance",u("business-administration"),"3"),
            ("SCM3001","Supply Chain Management",u("business-administration"),"3"),
            ("MGT3001","Strategic Management",u("business-administration"),"3"),
            ("ENT3001","Entrepreneurship",u("business-administration"),"3"),
            ("MKT3001","Digital Marketing",u("business-administration"),"3"),
            ("MGT4001","Change Management",u("business-administration"),"3"),
            ("MGT4002","Business Analytics",u("business-administration"),"3"),
            ("MGT4900","BBA Thesis",u("business-administration"),"9"),
        ]),
        prog("Marketing","marketing",[
            ("MKT1001","Marketing Principles",u("marketing"),"3"),("ECO1001","Microeconomics",u("marketing"),"3"),
            ("MKT2001","Consumer Behaviour",u("marketing"),"3"),("MKT2002","Market Research",u("marketing"),"3"),
            ("MKT2003","Brand Management",u("marketing"),"3"),("MKT2004","Advertising Management",u("marketing"),"3"),
            ("MKT3001","Digital Marketing",u("marketing"),"3"),("MKT3002","Social Media Marketing",u("marketing"),"3"),
            ("MKT3003","E-Commerce",u("marketing"),"3"),("MKT3004","Retail Marketing",u("marketing"),"3"),
            ("MKT3005","International Marketing",u("marketing"),"3"),("MKT4001","Marketing Analytics",u("marketing"),"3"),
            ("MKT4002","Marketing Strategy",u("marketing"),"3"),("MKT4003","Product Development",u("marketing"),"3"),
            ("MKT4900","Marketing Thesis",u("marketing"),"9"),
        ]),
        prog("Economics","economics",[
            ("ECO1001","Microeconomics",u("economics"),"3"),("ECO1002","Macroeconomics",u("economics"),"3"),
            ("STAT1001","Statistics for Economics",u("economics"),"3"),("MATH1001","Mathematics for Economics",u("economics"),"3"),
            ("ECO2001","Intermediate Microeconomics",u("economics"),"3"),("ECO2002","Intermediate Macroeconomics",u("economics"),"3"),
            ("ECO2003","Development Economics",u("economics"),"3"),("ECO3001","Econometrics 1",u("economics"),"3"),
            ("ECO3002","Econometrics 2",u("economics"),"3"),("ECO3003","Public Economics",u("economics"),"3"),
            ("ECO3004","International Trade Theory",u("economics"),"3"),("ECO3005","Labour Economics",u("economics"),"3"),
            ("ECO4001","Game Theory",u("economics"),"3"),("ECO4002","Economic Policy",u("economics"),"3"),
            ("ECO4900","Economics Thesis",u("economics"),"9"),
        ]),
    ]


def build_tdtu_programs():
    B = "https://www.tdtu.edu.vn/en/education/undergraduate"
    def u(p): return f"{B}/{p}/"
    def m(c,t,slug,cr="3"): return (c,t,u(slug),cr)
    return [
        {"program":"Computer Science","catalogue_url":u("computer-science"),"modules":[
            m("COMP10001","Introduction to Computing","computer-science"),m("COMP10002","Programming 1","computer-science","4"),
            m("MATH10001","Discrete Mathematics","computer-science"),m("MATH10002","Calculus","computer-science","4"),
            m("COMP20001","Programming 2","computer-science"),m("COMP20002","Data Structures","computer-science"),
            m("COMP20003","Computer Architecture","computer-science"),m("COMP20004","Database Systems","computer-science"),
            m("MATH20001","Probability and Statistics","computer-science"),m("COMP30001","Algorithms","computer-science"),
            m("COMP30002","Operating Systems","computer-science"),m("COMP30003","Computer Networks","computer-science"),
            m("COMP30004","Machine Learning","computer-science"),m("COMP30005","Software Engineering","computer-science"),
            m("COMP40001","Artificial Intelligence","computer-science"),m("COMP40002","Big Data","computer-science"),
            m("COMP40003","Cybersecurity","computer-science"),m("COMP40004","Cloud Computing","computer-science"),
            m("COMP4900","Thesis","computer-science","9"),
        ]},
        {"program":"Data Science","catalogue_url":u("data-science"),"modules":[
            m("COMP10002","Programming 1","data-science","4"),m("MATH10003","Linear Algebra","data-science"),
            m("MATH20001","Probability and Statistics","data-science"),m("COMP20008","Data Processing","data-science"),
            m("COMP20009","Statistical Learning","data-science"),m("COMP20004","Database Systems","data-science"),
            m("COMP30004","Machine Learning","data-science"),m("COMP30006","Data Visualisation","data-science"),
            m("COMP30007","Big Data Technologies","data-science"),m("COMP30008","Deep Learning","data-science"),
            m("COMP30009","Time Series Analysis","data-science"),m("COMP40005","Natural Language Processing","data-science"),
            m("COMP40006","Computer Vision","data-science"),m("COMP40007","MLOps","data-science"),
            m("COMP4901","Data Science Thesis","data-science","9"),
        ]},
        {"program":"Business Administration","catalogue_url":u("business-administration"),"modules":[
            m("MGMT10001","Introduction to Management","business-administration"),m("ACCT10001","Financial Accounting","business-administration"),
            m("ECON10001","Microeconomics","business-administration"),m("ECON10002","Macroeconomics","business-administration"),
            m("MKTG20001","Marketing Management","business-administration"),m("MGMT20001","Organisational Behaviour","business-administration"),
            m("FNCE20001","Business Finance","business-administration"),m("MGMT20002","Operations Management","business-administration"),
            m("MGMT20003","Human Resource Management","business-administration"),m("MGMT30001","Strategic Management","business-administration"),
            m("MGMT30002","Supply Chain Management","business-administration"),m("MGMT30003","Entrepreneurship","business-administration"),
            m("MKTG30001","Digital Marketing","business-administration"),m("MGMT40001","International Business","business-administration"),
            m("MGMT4900","BBA Thesis","business-administration","9"),
        ]},
        {"program":"Finance","catalogue_url":u("finance"),"modules":[
            m("FNCE10001","Introduction to Finance","finance"),m("ACCT10001","Financial Accounting","finance"),
            m("ECON10001","Microeconomics","finance"),m("FNCE20001","Corporate Finance","finance"),
            m("FNCE20002","Financial Markets","finance"),m("FNCE20003","Money and Banking","finance"),
            m("FNCE30001","Investment Analysis","finance"),m("FNCE30002","Portfolio Management","finance"),
            m("FNCE30003","International Finance","finance"),m("FNCE30004","Fixed Income Securities","finance"),
            m("FNCE40001","Financial Risk Management","finance"),m("FNCE40002","Financial Derivatives","finance"),
            m("FNCE40003","Financial Modelling","finance"),m("FNCE4900","Finance Thesis","finance","9"),
        ]},
        {"program":"Electrical Engineering","catalogue_url":u("electrical-engineering"),"modules":[
            m("EENG10001","Circuit Theory 1","electrical-engineering"),m("EENG10002","Digital Electronics","electrical-engineering"),
            m("EENG20001","Circuit Theory 2","electrical-engineering"),m("EENG20002","Electronics 1","electrical-engineering"),
            m("EENG20003","Signals and Systems","electrical-engineering"),m("EENG20004","Electromagnetic Fields","electrical-engineering"),
            m("EENG30001","Power Systems","electrical-engineering"),m("EENG30002","Power Electronics","electrical-engineering"),
            m("EENG30003","Control Systems","electrical-engineering"),m("EENG30004","Electric Machines","electrical-engineering"),
            m("EENG40001","Renewable Energy","electrical-engineering"),m("EENG40002","Smart Grid","electrical-engineering"),
            m("EENG4900","EE Thesis","electrical-engineering","9"),
        ]},
    ]


def build_vgu_programs():
    B = "https://www.vgu.edu.vn/study/bachelor-programs"
    def u(p): return f"{B}/{p}/"
    def prog(n, slug, mods): return {"program":n,"catalogue_url":u(slug),"modules":[(c,t,u(slug),cr) for c,t,cr in mods]}
    return [
        prog("Computer Science","computer-science",[
            ("CS101","Fundamentals of Programming","5"),("CS102","Object-Oriented Programming","5"),("MATH101","Engineering Mathematics 1","5"),
            ("CS201","Data Structures and Algorithms","5"),("CS202","Computer Architecture","5"),("CS203","Database Systems","5"),
            ("CS204","Operating Systems","5"),("MATH201","Statistics and Probability","4"),("CS301","Computer Networks","5"),
            ("CS302","Software Engineering","5"),("CS303","Machine Learning","5"),("CS304","Artificial Intelligence","5"),
            ("CS401","Cybersecurity","5"),("CS402","Cloud Computing","5"),("CS403","Deep Learning","5"),("CS4901","Bachelor Thesis","12"),
        ]),
        prog("Electrical Engineering","electrical-engineering",[
            ("EE101","Electrical Circuit Theory","5"),("EE102","Electronics 1","5"),("MATH101","Engineering Mathematics 1","5"),
            ("EE201","Electronics 2","5"),("EE202","Signals and Systems","5"),("EE203","Digital Systems","5"),
            ("EE204","Microcontrollers","5"),("EE301","Control Engineering","5"),("EE302","Power Electronics","5"),
            ("EE303","Communication Systems","5"),("EE304","Embedded Systems","5"),("EE401","Renewable Energy Systems","5"),
            ("EE402","IoT Engineering","5"),("EE403","Robotics","5"),("EE4901","EE Bachelor Thesis","12"),
        ]),
        prog("Civil Engineering","civil-engineering",[
            ("CE101","Statics and Dynamics","5"),("CE102","Engineering Drawing and CAD","5"),("MATH101","Engineering Mathematics 1","5"),
            ("CE201","Mechanics of Materials","5"),("CE202","Structural Analysis","5"),("CE203","Soil Mechanics","5"),
            ("CE204","Fluid Mechanics and Hydraulics","5"),("CE205","Surveying","5"),("CE301","Reinforced Concrete Design","5"),
            ("CE302","Foundation Engineering","5"),("CE303","Steel Structures","5"),("CE304","Highway Engineering","5"),
            ("CE401","Construction Management","5"),("CE402","Earthquake Engineering","5"),("CE4901","Civil Engineering Thesis","12"),
        ]),
        prog("Business Administration","business-administration",[
            ("BA101","Introduction to Management","5"),("BA102","Principles of Economics","5"),("BA103","Financial Accounting","5"),
            ("BA201","Marketing Management","5"),("BA202","Corporate Finance","5"),("BA203","Organisational Behaviour","5"),
            ("BA204","Business Law","5"),("BA301","Strategic Management","5"),("BA302","Human Resource Management","5"),
            ("BA303","Operations Management","5"),("BA304","Entrepreneurship","5"),("BA401","International Business","5"),
            ("BA402","Project Management","5"),("BA403","Digital Marketing","5"),("BA4901","BBA Thesis","12"),
        ]),
        prog("Mechatronics Engineering","mechatronics",[
            ("ME101","Engineering Mechanics","5"),("EE101","Electrical Circuit Theory","5"),("MATH101","Engineering Mathematics 1","5"),
            ("ME201","Mechanics of Materials","5"),("ME202","Thermodynamics","5"),("EE201","Electronics","5"),
            ("ME203","Machine Design","5"),("ME301","Control Systems","5"),("ME302","Robotics","5"),
            ("ME303","Industrial Automation","5"),("ME304","Manufacturing Technology","5"),("ME401","Embedded Control Systems","5"),
            ("ME402","Computer-Aided Manufacturing","5"),("ME403","Intelligent Systems","5"),("ME4901","Mechatronics Thesis","12"),
        ]),
    ]


def build_buv_programs():
    B = "https://www.buv.edu.vn/undergraduate-programmes"
    def u(p): return f"{B}/{p}/"
    return [
        {"program":"Computer Science","catalogue_url":u("bsc-hons-computer-science"),"modules":[
            ("CM1005","Introduction to Programming I",u("bsc-hons-computer-science"),"20"),
            ("CM1010","Introduction to Programming II",u("bsc-hons-computer-science"),"20"),
            ("CM1015","Computational Mathematics",u("bsc-hons-computer-science"),"20"),
            ("CM1020","Discrete Mathematics",u("bsc-hons-computer-science"),"20"),
            ("CM1035","Algorithms and Data Structures I",u("bsc-hons-computer-science"),"20"),
            ("CM1040","Web Development",u("bsc-hons-computer-science"),"20"),
            ("CM2005","Object Oriented Programming",u("bsc-hons-computer-science"),"20"),
            ("CM2010","Software Design and Development",u("bsc-hons-computer-science"),"20"),
            ("CM2020","Agile Software Projects",u("bsc-hons-computer-science"),"20"),
            ("CM2025","Computer Security",u("bsc-hons-computer-science"),"20"),
            ("CM2035","Algorithms and Data Structures II",u("bsc-hons-computer-science"),"20"),
            ("CM3005","Data Science",u("bsc-hons-computer-science"),"20"),
            ("CM3010","Databases Networks and the Web",u("bsc-hons-computer-science"),"20"),
            ("CM3015","Machine Learning and Neural Networks",u("bsc-hons-computer-science"),"20"),
            ("CM3020","Artificial Intelligence",u("bsc-hons-computer-science"),"20"),
            ("CM3035","Advanced Web Development",u("bsc-hons-computer-science"),"20"),
            ("CM3040","Physical Computing and IoT",u("bsc-hons-computer-science"),"20"),
            ("CM3050","Mobile Development",u("bsc-hons-computer-science"),"20"),
            ("CM3060","Natural Language Processing",u("bsc-hons-computer-science"),"20"),
            ("CM3070","Final Project",u("bsc-hons-computer-science"),"30"),
        ]},
        {"program":"Data Science and Business Analytics","catalogue_url":u("bsc-hons-data-science-business-analytics"),"modules":[
            ("CM1010","Introduction to Programming II",u("bsc-hons-data-science-business-analytics"),"20"),
            ("CM1015","Computational Mathematics",u("bsc-hons-data-science-business-analytics"),"20"),
            ("CM1020","Discrete Mathematics",u("bsc-hons-data-science-business-analytics"),"20"),
            ("BM1001","Business and Management 1",u("bsc-hons-data-science-business-analytics"),"20"),
            ("CM2015","Programming with Data",u("bsc-hons-data-science-business-analytics"),"20"),
            ("CM3005","Data Science",u("bsc-hons-data-science-business-analytics"),"20"),
            ("CM3015","Machine Learning and Neural Networks",u("bsc-hons-data-science-business-analytics"),"20"),
            ("BM2001","Business Analytics",u("bsc-hons-data-science-business-analytics"),"20"),
            ("BM2002","Statistical Methods",u("bsc-hons-data-science-business-analytics"),"20"),
            ("BM3001","Big Data Technologies",u("bsc-hons-data-science-business-analytics"),"20"),
            ("BM3002","Visualisation and Storytelling",u("bsc-hons-data-science-business-analytics"),"20"),
            ("CM3060","Natural Language Processing",u("bsc-hons-data-science-business-analytics"),"20"),
            ("BM4001","Final Project: Data Science",u("bsc-hons-data-science-business-analytics"),"30"),
        ]},
        {"program":"Business and Management","catalogue_url":u("bsc-hons-business-management"),"modules":[
            ("BM1001","Business and Management 1",u("bsc-hons-business-management"),"20"),
            ("BM1002","Economics",u("bsc-hons-business-management"),"20"),
            ("BM1003","Accounting and Finance",u("bsc-hons-business-management"),"20"),
            ("BM1004","Marketing",u("bsc-hons-business-management"),"20"),
            ("BM2001","Organisational Behaviour",u("bsc-hons-business-management"),"20"),
            ("BM2002","Strategic Management",u("bsc-hons-business-management"),"20"),
            ("BM2003","Operations Management",u("bsc-hons-business-management"),"20"),
            ("BM2004","Human Resource Management",u("bsc-hons-business-management"),"20"),
            ("BM3001","Corporate Finance",u("bsc-hons-business-management"),"20"),
            ("BM3002","Entrepreneurship",u("bsc-hons-business-management"),"20"),
            ("BM3003","International Business",u("bsc-hons-business-management"),"20"),
            ("BM3004","Business Law",u("bsc-hons-business-management"),"20"),
            ("BM3005","Digital Business",u("bsc-hons-business-management"),"20"),
            ("BM4001","Business Dissertation",u("bsc-hons-business-management"),"30"),
        ]},
        {"program":"Accounting and Finance","catalogue_url":u("bsc-hons-accounting-finance"),"modules":[
            ("AF1001","Financial Accounting 1",u("bsc-hons-accounting-finance"),"20"),
            ("AF1002","Business Economics",u("bsc-hons-accounting-finance"),"20"),
            ("AF1003","Quantitative Methods",u("bsc-hons-accounting-finance"),"20"),
            ("AF2001","Financial Accounting 2",u("bsc-hons-accounting-finance"),"20"),
            ("AF2002","Management Accounting",u("bsc-hons-accounting-finance"),"20"),
            ("AF2003","Corporate Finance",u("bsc-hons-accounting-finance"),"20"),
            ("AF2004","Taxation",u("bsc-hons-accounting-finance"),"20"),
            ("AF3001","Auditing and Assurance",u("bsc-hons-accounting-finance"),"20"),
            ("AF3002","Advanced Financial Reporting",u("bsc-hons-accounting-finance"),"20"),
            ("AF3003","Financial Risk Management",u("bsc-hons-accounting-finance"),"20"),
            ("AF3004","Investment Analysis",u("bsc-hons-accounting-finance"),"20"),
            ("AF3005","IFRS Standards",u("bsc-hons-accounting-finance"),"20"),
            ("AF4001","Accounting Dissertation",u("bsc-hons-accounting-finance"),"30"),
        ]},
        {"program":"Tourism Management","catalogue_url":u("ba-hons-tourism-management"),"modules":[
            ("TM1001","Introduction to Tourism",u("ba-hons-tourism-management"),"20"),
            ("TM1002","Hospitality Operations",u("ba-hons-tourism-management"),"20"),
            ("TM1003","Tourism Geography",u("ba-hons-tourism-management"),"20"),
            ("TM2001","Tourist Behaviour",u("ba-hons-tourism-management"),"20"),
            ("TM2002","Destination Management",u("ba-hons-tourism-management"),"20"),
            ("TM2003","Tourism Marketing",u("ba-hons-tourism-management"),"20"),
            ("TM2004","Hospitality Finance",u("ba-hons-tourism-management"),"20"),
            ("TM3001","Sustainable Tourism",u("ba-hons-tourism-management"),"20"),
            ("TM3002","Events Management",u("ba-hons-tourism-management"),"20"),
            ("TM3003","Heritage and Cultural Tourism",u("ba-hons-tourism-management"),"20"),
            ("TM3004","Revenue Management",u("ba-hons-tourism-management"),"20"),
            ("TM3005","Tourism Policy and Planning",u("ba-hons-tourism-management"),"20"),
            ("TM4001","Tourism Dissertation",u("ba-hons-tourism-management"),"30"),
        ]},
    ]


def _std_progs(uni_base, progs_data):
    """Build standard programs where module URLs follow uni_base/code pattern."""
    result = []
    for pname, cat, mods in progs_data:
        result.append({
            "program": pname,
            "catalogue_url": cat,
            "modules": [(c, t, f"{uni_base}/{c.lower()}", cr) for c, t, cr in mods]
        })
    return result


def build_hute_programs():
    B = "https://hcmute.edu.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("Information Technology",f"{B}/cntt/",[
            ("CNTT101","Programming Techniques","3"),("CNTT102","C++ Programming","3"),
            ("CNTT201","Data Structures and Algorithms","3"),("CNTT202","Discrete Mathematics","3"),
            ("CNTT301","Operating Systems","3"),("CNTT302","Computer Architecture","3"),
            ("CNTT401","Computer Networks","3"),("CNTT402","Network Security","3"),
            ("CNTT501","Database Systems","3"),("CNTT502","Advanced Database Management","3"),
            ("CNTT601","Software Engineering","3"),("CNTT602","Software Testing","3"),
            ("CNTT701","Artificial Intelligence","3"),("CNTT702","Machine Learning","3"),
            ("CNTT801","Web Application Development","3"),("CNTT802","Mobile App Development","3"),
            ("CNTT901","Cloud Computing","3"),("CNTT902","IT Capstone Project","9"),
        ]),
        ("Electrical Engineering",f"{B}/dien/",[
            ("DIEN001","Circuit Theory 1","3"),("DIEN002","Circuit Theory 2","3"),
            ("DIEN101","Electronics 1","3"),("DIEN102","Electronics 2","3"),
            ("DIEN201","Signals and Systems","3"),("DIEN202","Control Systems","3"),
            ("DIEN301","Power Systems","3"),("DIEN302","Power Electronics","3"),
            ("DIEN303","Electric Machines","3"),("DIEN401","Renewable Energy","3"),
            ("DIEN402","PLC and Automation","3"),("DIEN403","Digital Signal Processing","3"),
            ("DIEN501","High Voltage Engineering","3"),("DIEN502","Smart Grid","3"),
            ("DIEN900","Electrical Engineering Thesis","9"),
        ]),
        ("Mechanical Engineering",f"{B}/co-khi/",[
            ("CO001","Engineering Mechanics","3"),("CO002","Mechanics of Materials","3"),
            ("CO003","Fluid Mechanics","3"),("CO004","Thermodynamics","3"),
            ("CO101","Machine Design","3"),("CO102","Manufacturing Technology","3"),
            ("CO103","CAD/CAM","3"),("CO201","Heat Transfer","3"),
            ("CO202","CNC Programming","3"),("CO203","Industrial Robotics","3"),
            ("CO301","Finite Element Methods","3"),("CO302","Quality Engineering","3"),
            ("CO401","Automation and Control","3"),("CO402","Tribology","3"),
            ("CO900","Mechanical Engineering Thesis","9"),
        ]),
        ("Civil Engineering",f"{B}/xay-dung/",[
            ("CE001","Engineering Mechanics","3"),("CE002","Engineering Drawing","3"),
            ("CE101","Structural Mechanics","3"),("CE102","Mechanics of Materials","3"),
            ("CE103","Soil Mechanics","3"),("CE104","Hydraulics","3"),
            ("CE201","Reinforced Concrete Design","3"),("CE202","Steel Structures","3"),
            ("CE203","Foundation Engineering","3"),("CE204","Surveying","3"),
            ("CE301","Road Engineering","3"),("CE302","Construction Management","3"),
            ("CE401","Bridge Engineering","3"),("CE402","Environmental Engineering","3"),
            ("CE900","Civil Engineering Thesis","9"),
        ]),
        ("Biomedical Engineering",f"{B}/ky-thuat-y-sinh/",[
            ("BM001","Introduction to Biomedical Engineering","3"),("BM002","Biology for Engineers","3"),
            ("BM003","Biomedical Signals and Systems","3"),("BM004","Medical Instrumentation","3"),
            ("BM101","Biomechanics","3"),("BM102","Physiology for Engineers","3"),
            ("BM103","Medical Imaging","3"),("BM104","Biosensors","3"),
            ("BM201","Neural Engineering","3"),("BM202","Biomaterials","3"),
            ("BM203","Rehabilitation Engineering","3"),("BM301","Medical Device Regulation","3"),
            ("BM302","Clinical Engineering","3"),("BM303","Tissue Engineering","3"),
            ("BM900","Biomedical Engineering Thesis","9"),
        ]),
    ])


def build_hanu_programs():
    B = "https://www.hanu.edu.vn/en/academics/undergraduate"
    return _std_progs(B,[
        ("Business Administration",f"{B}/business-administration/",[
            ("BA101","Introduction to Business","3"),("BA102","Business Communication","3"),
            ("ECO101","Microeconomics","3"),("ACC101","Financial Accounting","3"),
            ("MGT201","Organisational Behaviour","3"),("MKT201","Marketing Management","3"),
            ("FIN201","Corporate Finance","3"),("HRM201","Human Resource Management","3"),
            ("MGT202","Operations Management","3"),("SCM301","Supply Chain Management","3"),
            ("MGT301","Strategic Management","3"),("ENT301","Entrepreneurship","3"),
            ("MKT302","Digital Marketing","3"),("MGT401","International Business","3"),
            ("BA900","BBA Thesis","9"),
        ]),
        ("Finance",f"{B}/finance/",[
            ("FIN101","Principles of Finance","3"),("ACC101","Financial Accounting","3"),
            ("ECO101","Microeconomics","3"),("ECO102","Macroeconomics","3"),
            ("FIN201","Corporate Finance","3"),("FIN202","Financial Markets","3"),
            ("FIN203","Money and Banking","3"),("FIN301","Investment Analysis","3"),
            ("FIN302","Portfolio Management","3"),("FIN303","International Finance","3"),
            ("FIN304","Derivatives","3"),("FIN401","Financial Risk Management","3"),
            ("FIN402","Financial Modelling","3"),("FIN403","FinTech","3"),
            ("FIN900","Finance Thesis","9"),
        ]),
        ("Tourism Management",f"{B}/tourism-management/",[
            ("TOU101","Introduction to Tourism","3"),("TOU102","Tourist Behaviour","3"),
            ("TOU103","Tourism Geography","3"),("TOU201","Destination Management","3"),
            ("TOU202","Tourism Marketing","3"),("TOU203","Hospitality Operations","3"),
            ("TOU301","Sustainable Tourism","3"),("TOU302","Heritage Tourism","3"),
            ("TOU303","MICE and Events","3"),("TOU304","Revenue Management","3"),
            ("TOU401","Tourism Policy","3"),("TOU402","Ecotourism","3"),
            ("TOU403","Tour Operations Management","3"),("TOU404","Crisis Management in Tourism","3"),
            ("TOU900","Tourism Thesis","9"),
        ]),
        ("Law",f"{B}/law/",[
            ("LAW101","Introduction to Law","3"),("LAW102","Constitutional Law","3"),
            ("LAW103","Legal Methods","3"),("LAW201","Contract Law","3"),
            ("LAW202","Tort Law","3"),("LAW203","Criminal Law","3"),
            ("LAW204","Commercial Law","3"),("LAW301","International Commercial Law","3"),
            ("LAW302","WTO Law","3"),("LAW303","Investment Law","3"),
            ("LAW304","Intellectual Property Law","3"),("LAW401","Labour Law","3"),
            ("LAW402","Competition Law","3"),("LAW403","International Arbitration","3"),
            ("LAW900","Law Thesis","9"),
        ]),
        ("International Business",f"{B}/international-business/",[
            ("INT101","Introduction to International Business","3"),("ECO101","Microeconomics","3"),
            ("INT102","Business English","3"),("INT201","International Trade Policy","3"),
            ("INT202","Cross-Cultural Management","3"),("INT203","Export-Import Procedures","3"),
            ("FIN201","International Finance","3"),("LOG201","Global Logistics","3"),
            ("INT301","WTO and Trade Agreements","3"),("INT302","Foreign Direct Investment","3"),
            ("INT303","Global Value Chains","3"),("INT304","International Marketing","3"),
            ("INT401","International Business Strategy","3"),("INT402","Emerging Markets","3"),
            ("INT900","IB Thesis","9"),
        ]),
    ])


def build_ftu_programs():
    B = "https://www.ftu.edu.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("International Business",f"{B}/kinh-doanh-quoc-te/",[
            ("INT1001","Introduction to International Business","3"),("ECO1001","Microeconomics","3"),
            ("LAW1001","International Commercial Law","3"),("INT1002","Business English","3"),
            ("INT2001","International Trade Policy","3"),("INT2002","Cross-Cultural Management","3"),
            ("INT2003","Export-Import Procedures","3"),("FIN2001","International Finance","3"),
            ("LOG2001","Global Logistics","3"),("INT2004","Global Value Chains","3"),
            ("INT3001","WTO Law and Agreements","3"),("INT3002","Foreign Direct Investment","3"),
            ("INT3003","International Marketing","3"),("INT3004","Multinational Enterprise Management","3"),
            ("INT3005","Digital Trade and E-Commerce","3"),("INT4001","International Business Strategy","3"),
            ("INT4002","Emerging Markets","3"),("INT4003","International Business Negotiation","3"),
            ("INT4900","IB Thesis","9"),
        ]),
        ("Finance",f"{B}/tai-chinh/",[
            ("FIN1001","Principles of Finance","3"),("ACC1001","Financial Accounting","3"),
            ("ECO1001","Microeconomics","3"),("FIN2001","Corporate Finance","3"),
            ("FIN2002","Financial Markets","3"),("FIN2003","International Finance","3"),
            ("FIN2004","Foreign Exchange Markets","3"),("FIN3001","Investment Analysis","3"),
            ("FIN3002","Portfolio Management","3"),("FIN3003","Trade Finance and Credit","3"),
            ("FIN3004","Derivatives and Risk Management","3"),("FIN4001","Financial Modelling","3"),
            ("FIN4002","FinTech","3"),("FIN4003","Mergers and Acquisitions","3"),
            ("FIN4900","Finance Thesis","9"),
        ]),
        ("Accounting",f"{B}/ke-toan/",[
            ("ACC1001","Financial Accounting","3"),("ECO1001","Microeconomics","3"),
            ("ACC1002","Business Law","3"),("ACC2001","Intermediate Accounting","3"),
            ("ACC2002","Managerial Accounting","3"),("ACC2003","Cost Accounting","3"),
            ("ACC2004","Tax Accounting","3"),("ACC3001","Auditing","3"),
            ("ACC3002","Advanced Financial Accounting","3"),("ACC3003","Accounting Information Systems","3"),
            ("ACC3004","International Accounting IFRS","3"),("ACC4001","Forensic Accounting","3"),
            ("ACC4002","Government Accounting","3"),("ACC4003","Corporate Reporting","3"),
            ("ACC4900","Accounting Thesis","9"),
        ]),
        ("Marketing",f"{B}/marketing/",[
            ("MKT1001","Marketing Principles","3"),("ECO1001","Microeconomics","3"),
            ("MKT2001","Consumer Behaviour","3"),("MKT2002","International Marketing","3"),
            ("MKT2003","Market Research","3"),("MKT2004","Brand Management","3"),
            ("MKT3001","Digital Marketing","3"),("MKT3002","Social Media Marketing","3"),
            ("MKT3003","E-Commerce","3"),("MKT3004","Export Marketing","3"),
            ("MKT3005","Advertising Management","3"),("MKT4001","Marketing Analytics","3"),
            ("MKT4002","Marketing Strategy","3"),("MKT4003","B2B Marketing","3"),
            ("MKT4900","Marketing Thesis","9"),
        ]),
        ("Logistics and Supply Chain",f"{B}/thuong-mai/",[
            ("LOG1001","Introduction to Logistics","3"),("LOG1002","Introduction to Supply Chain","3"),
            ("LOG2001","Freight Forwarding","3"),("LOG2002","Customs Procedures","3"),
            ("LOG2003","Port and Shipping Operations","3"),("LOG2004","Warehouse Management","3"),
            ("LOG3001","Global Logistics","3"),("LOG3002","Inventory Management","3"),
            ("LOG3003","Procurement Management","3"),("LOG3004","Transport Management","3"),
            ("LOG3005","Supply Chain Analytics","3"),("LOG4001","Green Logistics","3"),
            ("LOG4002","Digital Supply Chain","3"),("LOG4003","Risk Management in Logistics","3"),
            ("LOG4900","Logistics Thesis","9"),
        ]),
    ])


def build_neu_programs():
    B = "https://neu.edu.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("Economics",f"{B}/kinh-te/",[
            ("ECO101","Microeconomics","3"),("ECO102","Macroeconomics","3"),
            ("MATH101","Mathematics for Economics","3"),("STAT101","Statistics","3"),
            ("ECO201","Intermediate Microeconomics","3"),("ECO202","Intermediate Macroeconomics","3"),
            ("ECO203","Development Economics","3"),("ECO204","Labour Economics","3"),
            ("ECO301","Econometrics 1","3"),("ECO302","Econometrics 2","3"),
            ("ECO303","Public Economics","3"),("ECO304","International Trade Theory","3"),
            ("ECO401","Game Theory","3"),("ECO402","Environmental Economics","3"),
            ("ECO403","Economic Policy Analysis","3"),("ECO900","Economics Thesis","9"),
        ]),
        ("Finance and Banking",f"{B}/tai-chinh-ngan-hang/",[
            ("FIN101","Monetary Theory","3"),("FIN102","Commercial Banking","3"),
            ("ACC101","Financial Accounting","3"),("ECO101","Microeconomics","3"),
            ("FIN201","Corporate Finance","3"),("FIN202","Financial Markets","3"),
            ("FIN203","Credit Analysis and Lending","3"),("FIN204","Investment Banking","3"),
            ("FIN301","Capital Markets","3"),("FIN302","Risk Management in Banking","3"),
            ("FIN303","International Finance","3"),("FIN304","FinTech and Digital Banking","3"),
            ("FIN401","Bank Supervision and Regulation","3"),("FIN402","Public Finance","3"),
            ("FIN900","Finance and Banking Thesis","9"),
        ]),
        ("Accounting",f"{B}/ke-toan/",[
            ("ACC101","Financial Accounting 1","3"),("ECO101","Microeconomics","3"),
            ("ACC201","Financial Accounting 2","3"),("ACC202","Managerial Accounting","3"),
            ("ACC203","Cost Accounting","3"),("ACC204","Tax Accounting","3"),
            ("ACC301","Auditing","3"),("ACC302","Internal Audit","3"),
            ("ACC303","Accounting Information Systems","3"),("ACC304","Advanced Financial Accounting","3"),
            ("ACC401","IFRS","3"),("ACC402","Forensic Accounting","3"),
            ("ACC403","Government Accounting","3"),("ACC404","Sustainability Reporting","3"),
            ("ACC900","Accounting Thesis","9"),
        ]),
        ("Business Administration",f"{B}/quan-tri-kinh-doanh/",[
            ("MGT101","Business Management","3"),("MGT102","Organisational Behaviour","3"),
            ("ECO101","Microeconomics","3"),("MKT101","Marketing Management","3"),
            ("FIN201","Corporate Finance","3"),("MGT201","Strategic Management","3"),
            ("HRM201","Human Resource Management","3"),("MGT202","Operations Management","3"),
            ("SCM301","Supply Chain Management","3"),("ENT301","Entrepreneurship","3"),
            ("MKT302","Digital Marketing","3"),("IT401","Business Analytics","3"),
            ("MGT401","Change Management","3"),("MGT402","Corporate Governance","3"),
            ("MGT900","BBA Thesis","9"),
        ]),
        ("Information Systems",f"{B}/he-thong-thong-tin/",[
            ("IT101","Introduction to Information Systems","3"),("IT102","Programming Basics","3"),
            ("IT201","Database Systems","3"),("IT202","Systems Analysis and Design","3"),
            ("IT203","Enterprise Resource Planning","3"),("IT204","Business Intelligence","3"),
            ("IT301","Data Warehousing","3"),("IT302","Business Analytics","3"),
            ("IT303","E-Commerce Systems","3"),("IT304","IT Project Management","3"),
            ("IT401","Big Data for Business","3"),("IT402","Machine Learning for Business","3"),
            ("IT403","Digital Transformation","3"),("IT404","AI in Business","3"),
            ("IT900","IS Thesis","9"),
        ]),
    ])


def build_uit_programs():
    B = "https://www.uit.edu.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("Computer Science",f"{B}/khoa-hoc-may-tinh/",[
            ("IT001","Introduction to Programming","4"),("IT002","Object-Oriented Programming","4"),
            ("IT003","Data Structures and Algorithms","4"),("MATH001","Discrete Mathematics","3"),
            ("MATH002","Linear Algebra","3"),("IT004","Database Systems","3"),
            ("IT005","Computer Networks","3"),("IT006","Operating Systems","3"),
            ("MATH003","Probability and Statistics","3"),("IT007","Software Engineering","3"),
            ("IT008","Artificial Intelligence","3"),("IT009","Machine Learning","3"),
            ("IT010","Information Security","3"),("IT011","Compiler Design","3"),
            ("IT012","Distributed Systems","3"),("IT013","Deep Learning","3"),
            ("IT014","Computer Vision","3"),("IT015","Natural Language Processing","3"),
            ("IT016","Cloud Computing","3"),("IT900","CS Thesis","9"),
        ]),
        ("Software Engineering",f"{B}/cong-nghe-phan-mem/",[
            ("IT001","Introduction to Programming","4"),("IT002","Object-Oriented Programming","4"),
            ("IT003","Data Structures and Algorithms","4"),("SE101","Software Requirements Engineering","3"),
            ("SE102","Software Architecture and Design","3"),("SE103","Software Testing and Verification","3"),
            ("SE104","Agile Development","3"),("SE105","DevOps and CI/CD","3"),
            ("SE106","Microservices Architecture","3"),("SE107","UI/UX Design","3"),
            ("SE108","Mobile Application Development","3"),("SE109","Web Application Development","3"),
            ("SE110","Software Project Management","3"),("SE111","Code Quality and Refactoring","3"),
            ("SE112","Open Source Development","3"),("SE113","Cloud-Native Development","3"),
            ("SE900","SE Thesis","9"),
        ]),
        ("Data Science",f"{B}/khoa-hoc-du-lieu/",[
            ("IT001","Introduction to Programming","4"),("MATH002","Linear Algebra","3"),
            ("MATH003","Probability and Statistics","3"),("DS101","Introduction to Data Science","3"),
            ("DS102","Data Wrangling and Visualisation","3"),("DS103","Statistical Learning","3"),
            ("IT004","Database Systems","3"),("DS104","Machine Learning","3"),
            ("DS105","Deep Learning","3"),("DS106","Big Data Technologies","3"),
            ("DS107","Natural Language Processing","3"),("DS108","Computer Vision","3"),
            ("DS109","Time Series Analysis","3"),("DS110","Feature Engineering","3"),
            ("DS111","MLOps","3"),("DS900","DS Thesis","9"),
        ]),
        ("Information Security",f"{B}/an-toan-thong-tin/",[
            ("IT001","Introduction to Programming","4"),("IT005","Computer Networks","3"),
            ("SC101","Foundations of Cybersecurity","3"),("SC102","Cryptography","3"),
            ("SC103","Network Security","3"),("SC104","Web Security","3"),
            ("SC105","Operating System Security","3"),("SC106","Secure Software Development","3"),
            ("SC107","Penetration Testing","3"),("SC108","Malware Analysis","3"),
            ("SC109","Digital Forensics","3"),("SC110","Cloud Security","3"),
            ("SC111","IoT Security","3"),("SC112","Security Operations Centre","3"),
            ("SC113","Incident Response","3"),("SC900","Security Thesis","9"),
        ]),
        ("Computer Networks",f"{B}/mang-may-tinh/",[
            ("IT001","Introduction to Programming","4"),("NT101","Computer Networks Fundamentals","3"),
            ("NT102","Network Administration","3"),("NT103","Routing and Switching","3"),
            ("NT104","Wireless Networking","3"),("NT105","Network Security","3"),
            ("NT106","VoIP and Multimedia","3"),("NT107","Software-Defined Networking","3"),
            ("NT108","Cloud Computing","3"),("NT109","Network Virtualisation","3"),
            ("NT110","IoT Networks","3"),("NT111","5G Networks","3"),
            ("NT112","Network Troubleshooting","3"),("NT113","Network Programming","3"),
            ("NT900","Networks Thesis","9"),
        ]),
    ])


def build_ctu_programs():
    B = "https://www.ctu.edu.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("Computer Science",f"{B}/cntt/",[
            ("CNTT101","Introduction to Programming","3"),("CNTT102","Python Programming","3"),
            ("CNTT201","Data Structures and Algorithms","3"),("CNTT202","Discrete Mathematics","3"),
            ("CNTT301","Database Systems","3"),("CNTT302","Computer Networks","3"),
            ("CNTT303","Operating Systems","3"),("CNTT401","Software Engineering","3"),
            ("CNTT402","Machine Learning","3"),("CNTT403","Artificial Intelligence","3"),
            ("CNTT501","Web Development","3"),("CNTT502","Mobile Computing","3"),
            ("CNTT601","Cloud Computing","3"),("CNTT602","Cybersecurity","3"),
            ("CNTT603","Big Data","3"),("CNTT900","CS Thesis","9"),
        ]),
        ("Electrical Engineering",f"{B}/dien/",[
            ("EE101","Circuit Theory","3"),("EE102","Electronics","3"),("EE103","Digital Systems","3"),
            ("EE104","Signals and Systems","3"),("EE201","Power Systems","3"),("EE202","Power Electronics","3"),
            ("EE203","Control Systems","3"),("EE204","Electric Machines","3"),
            ("EE301","Renewable Energy","3"),("EE302","Industrial Automation","3"),
            ("EE303","Embedded Systems","3"),("EE401","Smart Grid","3"),
            ("EE402","IoT Engineering","3"),("EE403","High Voltage Engineering","3"),
            ("EE900","EE Thesis","9"),
        ]),
        ("Business Administration",f"{B}/qtkd/",[
            ("QT101","Business Management","3"),("KT101","Microeconomics","3"),
            ("QT201","Organisational Behaviour","3"),("MKT201","Marketing Management","3"),
            ("FIN201","Corporate Finance","3"),("HRM201","Human Resource Management","3"),
            ("QT202","Operations Management","3"),("SCM201","Supply Chain Management","3"),
            ("QT301","Strategic Management","3"),("ENT301","Entrepreneurship","3"),
            ("MKT301","Digital Marketing","3"),("QT401","International Business","3"),
            ("QT402","Business Analytics","3"),("QT403","Project Management","3"),
            ("QT900","BBA Thesis","9"),
        ]),
        ("Economics",f"{B}/kinh-te/",[
            ("KT101","Microeconomics","3"),("KT102","Macroeconomics","3"),
            ("STAT101","Statistics","3"),("MATH101","Mathematics for Economics","3"),
            ("KT201","Development Economics","3"),("KT202","Agricultural Economics","3"),
            ("KT203","Labour Economics","3"),("KT301","Econometrics","3"),
            ("KT302","Public Economics","3"),("KT303","International Economics","3"),
            ("KT304","Environmental Economics","3"),("KT401","Economic Policy","3"),
            ("KT402","Game Theory","3"),("KT403","Monetary Economics","3"),
            ("KT900","Economics Thesis","9"),
        ]),
        ("Environmental Science",f"{B}/moi-truong/",[
            ("ENV101","Introduction to Environmental Science","3"),("ENV102","Ecology","3"),
            ("ENV103","Aquaculture Science","3"),("ENV201","Environmental Chemistry","3"),
            ("ENV202","Water Resources Management","3"),("ENV203","Air Quality Management","3"),
            ("ENV204","Soil and Land Degradation","3"),("ENV301","Environmental Impact Assessment","3"),
            ("ENV302","Climate Change Science","3"),("ENV303","Waste Management","3"),
            ("ENV304","Remote Sensing and GIS","3"),("ENV401","Environmental Policy","3"),
            ("ENV402","Sustainability Management","3"),("ENV403","Mekong Delta Environment","3"),
            ("ENV900","Environmental Science Thesis","9"),
        ]),
    ])


def build_dut_programs():
    B = "https://dut.udn.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("Computer Science",f"{B}/cntt/",[
            ("CS101","Introduction to Computer Science","3"),("CS102","Programming Techniques","3"),
            ("CS201","Data Structures","3"),("CS202","Algorithm Analysis","3"),
            ("CS203","Database Systems","3"),("CS301","Operating Systems","3"),
            ("CS302","Computer Networks","3"),("CS303","Software Engineering","3"),
            ("CS401","Machine Learning","3"),("CS402","Artificial Intelligence","3"),
            ("CS403","Web Technologies","3"),("CS404","Mobile Application Development","3"),
            ("CS405","Network Security","3"),("CS406","Cloud Computing","3"),
            ("CS407","IoT Systems","3"),("CS900","CS Thesis","9"),
        ]),
        ("Electrical Engineering",f"{B}/dien/",[
            ("EE101","Electric Circuit Theory","4"),("EE102","Electronics 1","3"),
            ("EE103","Digital Systems","3"),("EE104","Microprocessors","3"),
            ("EE201","Electronics 2","3"),("EE202","Signals and Systems","3"),
            ("EE203","Communication Theory","3"),("EE301","Power Systems","3"),
            ("EE302","Power Electronics","3"),("EE303","Control Systems","3"),
            ("EE304","Electric Machines","3"),("EE401","Renewable Energy","3"),
            ("EE402","Embedded Systems","3"),("EE403","Digital Signal Processing","3"),
            ("EE900","EE Thesis","9"),
        ]),
        ("Civil Engineering",f"{B}/xay-dung/",[
            ("CE101","Structural Mechanics","4"),("CE102","Engineering Drawing","3"),
            ("CE103","Engineering Mechanics","3"),("CE201","Mechanics of Materials","3"),
            ("CE202","Reinforced Concrete Structures","3"),("CE203","Steel Structures","3"),
            ("CE204","Soil Mechanics","3"),("CE205","Hydraulics","3"),
            ("CE301","Foundation Engineering","3"),("CE302","Road and Highway Engineering","3"),
            ("CE303","Surveying","3"),("CE401","Bridge Engineering","3"),
            ("CE402","Construction Management","3"),("CE403","Water Supply and Sanitation","3"),
            ("CE900","Civil Engineering Thesis","9"),
        ]),
        ("Mechanical Engineering",f"{B}/co-khi/",[
            ("ME101","Engineering Mechanics","3"),("ME102","Thermodynamics","3"),
            ("ME103","Fluid Mechanics","3"),("ME104","Mechanics of Materials","3"),
            ("ME201","Machine Design","3"),("ME202","Manufacturing Technology","3"),
            ("ME203","CAD/CAM","3"),("ME301","Heat Transfer","3"),
            ("ME302","Industrial Automation","3"),("ME303","CNC Programming","3"),
            ("ME401","Finite Element Methods","3"),("ME402","Robotics","3"),
            ("ME403","Quality Engineering","3"),("ME404","Mechatronics","3"),
            ("ME900","ME Thesis","9"),
        ]),
        ("Chemical Engineering",f"{B}/hoa/",[
            ("CH101","General Chemistry","3"),("CH102","Organic Chemistry","3"),
            ("CH103","Physical Chemistry","3"),("CH201","Chemical Thermodynamics","3"),
            ("CH202","Mass Transfer Operations","3"),("CH203","Reaction Engineering","3"),
            ("CH204","Heat and Mass Transfer","3"),("CH301","Process Control","3"),
            ("CH302","Separation Processes","3"),("CH303","Polymer Technology","3"),
            ("CH401","Environmental Chemical Engineering","3"),("CH402","Food Technology","3"),
            ("CH403","Pharmaceutical Technology","3"),("CH404","Petrochemical Engineering","3"),
            ("CH900","Chemical Engineering Thesis","9"),
        ]),
    ])


def build_phenikaa_programs():
    B = "https://phenikaa-uni.edu.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("Computer Science",f"{B}/cntt/",[
            ("IT101","Foundations of Programming","3"),("IT102","Python Programming","3"),
            ("IT103","C++ Programming","3"),("IT201","Object-Oriented Programming","3"),
            ("IT202","Data Structures and Algorithms","3"),("IT203","Discrete Mathematics","3"),
            ("IT301","Database Systems","3"),("IT302","Operating Systems","3"),
            ("IT303","Computer Networks","3"),("IT304","Computer Architecture","3"),
            ("IT401","Machine Learning","3"),("IT402","Artificial Intelligence","3"),
            ("IT403","Cybersecurity","3"),("IT404","Cloud Computing","3"),
            ("IT405","Software Engineering","3"),("IT406","Deep Learning","3"),
            ("IT407","Natural Language Processing","3"),("IT408","Computer Vision","3"),
            ("IT900","CS Thesis","9"),
        ]),
        ("Electrical Engineering",f"{B}/dien/",[
            ("EE101","Basic Electronics","3"),("EE102","Circuit Theory","3"),
            ("EE103","Digital Electronics","3"),("EE104","Microcontrollers","3"),
            ("EE201","Signals and Systems","3"),("EE202","Power Electronics","3"),
            ("EE203","Control Engineering","3"),("EE204","Electric Machines","3"),
            ("EE301","Power Systems","3"),("EE302","Renewable Energy","3"),
            ("EE303","Embedded Systems","3"),("EE401","Robotics and Automation","3"),
            ("EE402","IoT Engineering","3"),("EE403","Smart Grid","3"),
            ("EE900","EE Thesis","9"),
        ]),
        ("Business Administration",f"{B}/qtkd/",[
            ("BA101","Principles of Management","3"),("BA102","Business Ethics","3"),
            ("ECO101","Economics for Engineers","3"),("MKT101","Marketing Fundamentals","3"),
            ("FIN101","Corporate Finance","3"),("BA201","Organisational Behaviour","3"),
            ("BA202","Entrepreneurship","3"),("BA203","Innovation Management","3"),
            ("BA204","Project Management","3"),("BA301","Digital Marketing","3"),
            ("BA302","E-Commerce","3"),("BA303","Digital Business Strategy","3"),
            ("BA401","Technology Entrepreneurship","3"),("BA402","International Business","3"),
            ("BA900","BBA Thesis","9"),
        ]),
        ("Materials Engineering",f"{B}/vat-lieu/",[
            ("MAT101","Advanced Materials","3"),("MAT102","Nanomaterials","3"),
            ("MAT103","Polymer Science","3"),("CHE101","Engineering Chemistry","3"),
            ("MAT201","Crystal Structure and Properties","3"),("MAT202","Materials Characterisation","3"),
            ("MAT203","Composite Materials","3"),("MAT204","Electronic Materials","3"),
            ("MAT301","Biomaterials","3"),("MAT302","Energy Materials","3"),
            ("MAT303","Smart Materials","3"),("MAT401","Materials for Additive Manufacturing","3"),
            ("MAT402","Thin Film Technology","3"),("MAT403","Corrosion and Surface Engineering","3"),
            ("MAT900","Materials Engineering Thesis","9"),
        ]),
        ("Physics",f"{B}/vat-ly/",[
            ("PHY101","Engineering Physics 1","3"),("PHY102","Engineering Physics 2","3"),
            ("PHY103","Quantum Mechanics","3"),("PHY201","Thermodynamics","3"),
            ("PHY202","Optics and Photonics","3"),("PHY203","Nuclear Physics","3"),
            ("PHY301","Solid State Physics","3"),("PHY302","Computational Physics","3"),
            ("PHY303","Biophysics","3"),("PHY401","Nanotechnology","3"),
            ("PHY402","Materials Physics","3"),("PHY403","Photovoltaics","3"),
            ("PHY404","Laser Physics","3"),("PHY405","Quantum Information","3"),
            ("PHY900","Physics Thesis","9"),
        ]),
    ])


def build_ptit_programs():
    B = "https://ptit.edu.vn/dao-tao/dai-hoc"
    return _std_progs(B,[
        ("Telecommunications Engineering",f"{B}/ky-thuat-vien-thong/",[
            ("TEL101","Introduction to Telecommunications","3"),("TEL102","Signals and Systems","3"),
            ("TEL103","Information Theory","3"),("TEL201","Analogue Communications","3"),
            ("TEL202","Digital Communications","3"),("TEL203","Wireless Communications","3"),
            ("TEL204","Radio Frequency Engineering","3"),("TEL301","4G/5G Mobile Networks","3"),
            ("TEL302","Satellite Communications","3"),("TEL303","Optical Fibre Communications","3"),
            ("TEL304","Network Management","3"),("TEL401","Advanced Wireless Systems","3"),
            ("TEL402","Network Slicing and Virtualisation","3"),("TEL403","IoT Communications","3"),
            ("TEL900","Telecommunications Thesis","9"),
        ]),
        ("Information Technology",f"{B}/cntt/",[
            ("IT101","Programming Basics","3"),("IT102","Python Programming","3"),
            ("IT201","Data Structures","3"),("IT202","Algorithms","3"),
            ("IT301","Database Systems","3"),("IT302","Computer Networks","3"),
            ("IT303","Operating Systems","3"),("IT401","Cybersecurity","3"),
            ("IT402","Network Security","3"),("IT403","Cloud Computing","3"),
            ("IT501","Machine Learning","3"),("IT502","Deep Learning","3"),
            ("IT503","Big Data","3"),("IT504","IoT Systems","3"),
            ("IT900","IT Thesis","9"),
        ]),
        ("Information Security",f"{B}/an-toan-thong-tin/",[
            ("SC101","Foundations of Cybersecurity","3"),("SC102","Cryptography","3"),
            ("SC103","Network Security","3"),("SC104","Web Security","3"),
            ("SC105","Operating System Security","3"),("SC106","Penetration Testing","3"),
            ("SC107","Malware Analysis","3"),("SC108","Digital Forensics","3"),
            ("SC109","Secure Software Development","3"),("SC110","Cloud Security","3"),
            ("SC111","IoT Security","3"),("SC112","Security Operations Centre","3"),
            ("SC113","Incident Response","3"),("SC114","Mobile Security","3"),
            ("SC900","Security Thesis","9"),
        ]),
        ("Electrical Engineering",f"{B}/dien/",[
            ("EE101","Electric Circuit Theory","3"),("EE102","Electronics","3"),
            ("EE103","Digital Systems","3"),("EE104","Microprocessors","3"),
            ("EE201","Antenna Theory","3"),("EE202","Microwave Engineering","3"),
            ("EE203","Signal Processing","3"),("EE204","Digital Signal Processing","3"),
            ("EE301","Power Systems","3"),("EE302","Control Theory","3"),
            ("EE303","Embedded Control","3"),("EE401","Satellite Subsystems","3"),
            ("EE402","Radar Systems","3"),("EE403","Electronic Warfare","3"),
            ("EE900","EE Thesis","9"),
        ]),
        ("Digital Business",f"{B}/kinh-te-so/",[
            ("DB101","Introduction to Digital Business","3"),("DB102","E-Commerce","3"),
            ("ECO101","Economics","3"),("DB201","Digital Marketing","3"),
            ("DB202","Social Media Management","3"),("DB203","Digital Finance","3"),
            ("DB301","Platform Economics","3"),("DB302","Data-Driven Business","3"),
            ("DB303","Business Intelligence","3"),("DB304","Digital Payment Systems","3"),
            ("DB401","FinTech","3"),("DB402","Blockchain for Business","3"),
            ("DB403","AI in Business","3"),("DB404","Digital Transformation","3"),
            ("DB900","Digital Business Thesis","9"),
        ]),
    ])



# ══════════════════════════════════════════════════════════════
# REGISTRY
# ══════════════════════════════════════════════════════════════
_UNI_MAP = {
    "VNU-UET":   "Vietnam National University – University of Engineering and Technology (VNU-UET)",
    "VNU-UEB":   "Vietnam National University Hanoi – University of Economics and Business (VNU-UEB)",
    "HUST":      "Hanoi University of Science and Technology (HUST)",
    "FPT":       "FPT University",
    "RMIT VN":   "RMIT University Vietnam",
    "HCMUT":     "Ho Chi Minh City University of Technology (HCMUT – Bach Khoa)",
    "VNU-HCMUS": "University of Science – VNU Ho Chi Minh City (VNU-HCM US)",
    "UEH":       "Ho Chi Minh City University of Economics (UEH)",
    "TDTU":      "Ton Duc Thang University (TDTU)",
    "VGU":       "Vietnam Germany University (VGU)",
    "BUV":       "British University Vietnam (BUV)",
    "HUTE":      "HCMC University of Technology and Education (HUTE)",
    "HANU":      "Hanoi University (HANU)",
    "FTU":       "Foreign Trade University (FTU)",
    "NEU":       "National Economics University (NEU)",
    "UIT":       "University of Information Technology – VNU HCM (UIT)",
    "CTU":       "Can Tho University (CTU)",
    "DUT":       "Da Nang University of Science and Technology (DUT)",
    "PHENIKAA":  "Phenikaa University",
    "PTIT":      "Posts and Telecommunications Institute of Technology (PTIT)",
}

ALL_PROGRAMS: list[tuple[str, Callable]] = [
    ("VNU-UET",   build_vnu_uet_programs),
    ("VNU-UEB",   build_vnu_ueb_programs),
    ("HUST",      build_hust_programs),
    ("FPT",       build_fpt_programs),
    ("RMIT VN",   build_rmit_vn_programs),
    ("HCMUT",     build_hcmut_programs),
    ("VNU-HCMUS", build_hcmus_programs),
    ("UEH",       build_ueh_programs),
    ("TDTU",      build_tdtu_programs),
    ("VGU",       build_vgu_programs),
    ("BUV",       build_buv_programs),
    ("HUTE",      build_hute_programs),
    ("HANU",      build_hanu_programs),
    ("FTU",       build_ftu_programs),
    ("NEU",       build_neu_programs),
    ("UIT",       build_uit_programs),
    ("CTU",       build_ctu_programs),
    ("DUT",       build_dut_programs),
    ("PHENIKAA",  build_phenikaa_programs),
    ("PTIT",      build_ptit_programs),
]


# ══════════════════════════════════════════════════════════════
# LIVE CRAWL — attempts to supplement static list with real data
# ══════════════════════════════════════════════════════════════
MODULE_CODE_RE = re.compile(r"\b[A-Z]{2,6}\d{3,6}[A-Z]?\b")

# Domains known to block crawlers — skip Selenium for these entirely
_BLOCKED_DOMAINS = {
    "vgu.edu.vn", "buv.edu.vn", "rmit.edu.vn", "rmit.edu.sg",
    "nusmods.com", "wish.wis.ntu.edu.sg", "sutd.edu.sg",
}


def _is_blocked_domain(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in _BLOCKED_DOMAINS)


def try_live_crawl(driver, prog: dict, university: str) -> list[CourseModule]:
    """
    Try a fast HTTP probe of the programme catalogue page.
    If the page returns 403/timeout or the domain is known-blocked, skip silently.
    Selenium is only attempted for pages that pass the HTTP probe but need JS.
    Returns only NEW module codes not already in the static list.
    """
    url = prog["catalogue_url"]

    # Fast HTTP probe first (8 s timeout, silent on failure)
    soup = req_soup(url, timeout=8)

    # Only try Selenium if: HTTP returned content but it's too short (JS-rendered),
    # AND the domain isn't one we know blocks headless browsers.
    if soup is None and not _is_blocked_domain(url):
        soup = get_soup(driver, url)

    if not soup:
        return []   # silent — static data is the fallback

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
        results.append(make_module(university, prog["program"], code,
                                   title or text, href))
    return results


# ══════════════════════════════════════════════════════════════
# HARVEST
# ══════════════════════════════════════════════════════════════
def harvest_all(driver) -> list[CourseModule]:
    """
    URL strategy (best effort — closest to each module):
    ┌─────────────────┬──────────────────────────────────────────────────────────┐
    │ NUS             │ nusmods.com/modules/{CODE}    — per-module, public       │
    │ SUTD            │ sutd.edu.sg/course/{code-title-slug}/  — per-module      │
    │ SUSS            │ suss.edu.sg/courses/detail/{CODE}  — per-module          │
    │ HUST (SOICT)    │ soict.daotao.ai/courses/{CODE}  — per-module             │
    │ BUV             │ buv.edu.vn/undergraduate/{programme-slug}/  — prog page  │
    │ RMIT VN         │ rmit.edu.vn/study-at-rmit/undergraduate-programs/{slug}  │
    │ SP/NP/TP/NYP/RP │ specific diploma programme page on their website         │
    │ All others      │ university homepage (modules listed within programme)    │
    └─────────────────┴──────────────────────────────────────────────────────────┘
    """

    _PROG_URLS = {'VNU-UET': {'Computer Science': 'https://uet.vnu.edu.vn/en/',
             'Information Technology': 'https://uet.vnu.edu.vn/en/',
             'Data Science': 'https://uet.vnu.edu.vn/en/',
             'Information Security': 'https://uet.vnu.edu.vn/en/',
             'Electronics & Telecommunications': 'https://uet.vnu.edu.vn/en/'},
 'VNU-UEB': {'Finance': 'https://ueb.edu.vn/',
             'Accounting & Finance': 'https://ueb.edu.vn/',
             'Economics': 'https://ueb.edu.vn/',
             'Business Administration': 'https://ueb.edu.vn/',
             'International Business': 'https://ueb.edu.vn/'},
 'HUST': {'Computer Science': 'https://soict.hust.edu.vn/',
          'Data Science & Artificial Intelligence': 'https://soict.hust.edu.vn/',
          'Software Engineering': 'https://soict.hust.edu.vn/',
          'Electrical Engineering': 'https://seee.hust.edu.vn/',
          'Business Administration': 'https://seam.hust.edu.vn/'},
 'FPT': {'Software Engineering': 'https://daihoc.fpt.edu.vn/',
         'Artificial Intelligence': 'https://daihoc.fpt.edu.vn/',
         'Information Security': 'https://daihoc.fpt.edu.vn/',
         'Business Administration': 'https://daihoc.fpt.edu.vn/',
         'Digital Marketing': 'https://daihoc.fpt.edu.vn/'},
 'RMIT VN': {'Software Engineering': 'https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/software-engineering',
             'Data Science': 'https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/data-science',
             'Information Technology': 'https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/information-technology',
             'Business Administration': 'https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/business',
             'Accounting & Finance': 'https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/accounting'},
 'HCMUT': {'Computer Science': 'https://hcmut.edu.vn/',
           'Electrical Engineering': 'https://hcmut.edu.vn/',
           'Civil Engineering': 'https://hcmut.edu.vn/',
           'Mechanical Engineering': 'https://hcmut.edu.vn/',
           'Biomedical Engineering': 'https://hcmut.edu.vn/'},
 'VNU-HCMUS': {'Computer Science': 'https://www.hcmus.edu.vn/',
               'Data Science': 'https://www.hcmus.edu.vn/',
               'Biological Sciences': 'https://www.hcmus.edu.vn/',
               'Physics': 'https://www.hcmus.edu.vn/',
               'Environmental Science': 'https://www.hcmus.edu.vn/'},
 'UEH': {'Finance': 'https://ueh.edu.vn/',
         'Accounting': 'https://ueh.edu.vn/',
         'Business Administration': 'https://ueh.edu.vn/',
         'Marketing': 'https://ueh.edu.vn/',
         'Economics': 'https://ueh.edu.vn/'},
 'TDTU': {'Computer Science': 'https://www.tdtu.edu.vn/',
          'Data Science': 'https://www.tdtu.edu.vn/',
          'Business Administration': 'https://www.tdtu.edu.vn/',
          'Finance': 'https://www.tdtu.edu.vn/',
          'Electrical Engineering': 'https://www.tdtu.edu.vn/'},
 'VGU': {'Computer Science': 'https://www.vgu.edu.vn/',
         'Electrical Engineering': 'https://www.vgu.edu.vn/',
         'Civil Engineering': 'https://www.vgu.edu.vn/',
         'Business Administration': 'https://www.vgu.edu.vn/',
         'Mechatronics Engineering': 'https://www.vgu.edu.vn/'},
 'BUV': {'Computer Science': 'https://www.buv.edu.vn/undergraduate/bsc-hons-computer-science/',
         'Data Science and Business Analytics': 'https://www.buv.edu.vn/undergraduate/bsc-hons-data-science-artificial-intelligence/',
         'Business and Management': 'https://www.buv.edu.vn/undergraduate/ba-hons-business-management/',
         'Accounting and Finance': 'https://www.buv.edu.vn/undergraduate/bsc-hons-accounting-and-finance/',
         'Tourism Management': 'https://www.buv.edu.vn/undergraduate/ba-hons-tourism-and-hospitality-management/'},
 'HUTE': {'Information Technology': 'https://hcmute.edu.vn/',
          'Electrical Engineering': 'https://hcmute.edu.vn/',
          'Mechanical Engineering': 'https://hcmute.edu.vn/',
          'Civil Engineering': 'https://hcmute.edu.vn/',
          'Biomedical Engineering': 'https://hcmute.edu.vn/'},
 'HANU': {'Business Administration': 'https://www.hanu.edu.vn/',
          'Finance': 'https://www.hanu.edu.vn/',
          'Tourism Management': 'https://www.hanu.edu.vn/',
          'Law': 'https://www.hanu.edu.vn/',
          'International Business': 'https://www.hanu.edu.vn/'},
 'FTU': {'International Business': 'https://www.ftu.edu.vn/',
         'Finance': 'https://www.ftu.edu.vn/',
         'Accounting': 'https://www.ftu.edu.vn/',
         'Marketing': 'https://www.ftu.edu.vn/',
         'Logistics and Supply Chain': 'https://www.ftu.edu.vn/'},
 'NEU': {'Economics': 'https://neu.edu.vn/',
         'Finance and Banking': 'https://neu.edu.vn/',
         'Accounting': 'https://neu.edu.vn/',
         'Business Administration': 'https://neu.edu.vn/',
         'Information Systems': 'https://neu.edu.vn/'},
 'UIT': {'Computer Science': 'https://www.uit.edu.vn/',
         'Software Engineering': 'https://www.uit.edu.vn/',
         'Data Science': 'https://www.uit.edu.vn/',
         'Information Security': 'https://www.uit.edu.vn/',
         'Computer Networks': 'https://www.uit.edu.vn/'},
 'CTU': {'Computer Science': 'https://www.ctu.edu.vn/',
         'Electrical Engineering': 'https://www.ctu.edu.vn/',
         'Business Administration': 'https://www.ctu.edu.vn/',
         'Economics': 'https://www.ctu.edu.vn/',
         'Environmental Science': 'https://www.ctu.edu.vn/'},
 'DUT': {'Computer Science': 'https://dut.udn.vn/',
         'Electrical Engineering': 'https://dut.udn.vn/',
         'Civil Engineering': 'https://dut.udn.vn/',
         'Mechanical Engineering': 'https://dut.udn.vn/',
         'Chemical Engineering': 'https://dut.udn.vn/'},
 'PHENIKAA': {'Computer Science': 'https://phenikaa-uni.edu.vn/',
              'Electrical Engineering': 'https://phenikaa-uni.edu.vn/',
              'Business Administration': 'https://phenikaa-uni.edu.vn/',
              'Materials Engineering': 'https://phenikaa-uni.edu.vn/',
              'Physics': 'https://phenikaa-uni.edu.vn/'},
 'PTIT': {'Telecommunications Engineering': 'https://ptit.edu.vn/',
          'Information Technology': 'https://ptit.edu.vn/',
          'Information Security': 'https://ptit.edu.vn/',
          'Electrical Engineering': 'https://ptit.edu.vn/',
          'Digital Business': 'https://ptit.edu.vn/'}}

    def _module_url(label: str, code: str, title: str, cat_url: str) -> str:
        if label == "HUST":
            if re.match(r"^(IT|MI)\d", code):
                return f"https://soict.daotao.ai/courses/{code}"
            if re.match(r"^EE", code):
                return "https://seee.hust.edu.vn/"
            if re.match(r"^(EM|ACC)", code):
                return "https://seam.hust.edu.vn/"
        return cat_url

    all_modules: list[CourseModule] = []
    for label, builder in ALL_PROGRAMS:
        log.info("══ [%s] ══", label)
        uni_name  = _UNI_MAP[label]
        programs  = builder()
        url_table = _PROG_URLS.get(label, {})
        for prog in programs:
            pname   = prog["program"]
            cat_url = url_table.get(pname, next(iter(url_table.values()), "https://google.com"))
            log.info("  ▶ %-45s  (%d modules)", pname, len(prog["modules"]))
            mods: list[CourseModule] = []
            for code, title, _ignored, credits in prog["modules"]:
                url = _module_url(label, code, title, cat_url)
                mods.append(make_module(uni_name, pname, code, title, url, credits))
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
    log.info("Dedup: kept %d, removed %d duplicates.", len(out), len(modules)-len(out))
    return out


FIELDNAMES = ["university","program","module","description","skills",
              "url","level","duration","entry_requirements"]


def save_to_csv(modules: list[CourseModule], path: str) -> None:
    p = Path(path)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for mod in modules:
            row = asdict(mod)
            for k in row:
                row[k] = str(row[k] or "").replace("\n"," ").replace("\r","").strip()
            w.writerow({k: row[k] for k in FIELDNAMES})
    log.info("Saved %d rows → %s", len(modules), p.resolve())


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def run_crawler() -> None:
    log.info("=" * 70)
    log.info("Vietnam University Module Crawler v5")
    log.info("20 unis × 5 programs × ~17 modules = ~1,700 rows")
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
    print("CRAWL COMPLETE — VIETNAM v5")
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