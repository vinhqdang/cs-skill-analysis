"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         GOOGLE × BUV SoCIT — Graduate Career Fit Analyzer                  ║
║         Based on real 2026 Google graduate job requirements                 ║
║         Works with all 5 BUV School of Computing & Innovative Tech degrees  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Requirements:
    pip install numpy matplotlib colorama tabulate

Run:
    python google_buv_career_fit.py
"""

import numpy as np
from tabulate import tabulate
from colorama import init, Fore, Style
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from math import pi

init(autoreset=True)  # colorama init

# ─────────────────────────────────────────────────────────────────────────────
# 1. SKILL DIMENSIONS
# ─────────────────────────────────────────────────────────────────────────────
SKILLS = [
    "Programming (Python/C++/Java)",
    "Algorithms & Data Structures",
    "Systems & Architecture",
    "Machine Learning / AI",
    "Data Analysis & Stats",
    "Databases & SQL",
    "Networking & Security",
    "Web / Full-Stack Dev",
    "UX & Product Design",
    "Cloud & Distributed Systems",
    "NLP / Computer Vision",
    "Soft Skills & Communication",
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. BUV SoCIT MODULE → SKILL VECTORS
#    Format: [prog, skill_0, skill_1, ..., skill_11]
# ─────────────────────────────────────────────────────────────────────────────
PROGRAMMES = {
    "BSc Data Science & AI (Stirling)": {
        "Introduction to Computing Science":  [1,1,1,0,0,0,0,0,0,0,0,1],
        "Discrete Structures":                [1,1,0,0,1,0,0,0,0,0,0,0],
        "Scripting for Data Science":         [1,0,0,0,0,0,0,0,0,0,0,0],
        "Programming & UI Design":            [1,0,0,0,0,0,0,1,1,0,0,0],
        "Introduction to Data Science":       [1,0,0,0,1,0,0,0,0,0,0,0],
        "Practical Statistics":               [0,0,0,0,1,0,0,0,0,0,0,0],
        "Database Principles & Applications": [0,0,0,0,0,1,0,0,0,0,0,0],
        "Introduction to Machine Learning":   [1,0,0,1,1,0,0,0,0,0,0,0],
        "UX Design":                          [0,0,0,0,0,0,0,0,1,0,0,0],
        "NoSQL Databases & Data Warehousing": [0,0,0,0,0,1,0,0,0,1,0,0],
        "NLP & Computer Vision":              [1,0,0,1,0,0,0,0,0,0,1,0],
        "Data Strategy":                      [0,0,0,0,0,0,0,0,0,0,0,1],
        "Distributed Data Science Systems":   [1,0,1,0,0,1,1,0,0,1,0,0],
        "Cyber Security":                     [0,0,1,0,0,0,1,0,0,0,0,0],
        "Artificial Intelligence":            [1,1,0,1,1,0,0,0,0,0,1,0],
        "Data Science Applications":          [1,0,0,1,1,1,0,0,0,0,0,0],
    },
    "BSc Software Engineering (Stirling)": {
        "Programming & Problem Solving":      [1,1,0,0,0,0,0,0,0,0,0,1],
        "Computer Systems & Networks":        [1,0,1,0,0,0,1,0,0,0,0,0],
        "Software Engineering Practice":      [1,1,0,0,0,0,0,0,0,0,0,1],
        "Web Technologies":                   [1,0,0,0,0,0,0,1,0,0,0,0],
        "Object-Oriented Development":        [1,1,0,0,0,0,0,0,0,0,0,0],
        "Databases":                          [0,0,0,0,0,1,0,0,0,0,0,0],
        "Algorithms & Data Structures":       [1,1,0,0,0,0,0,0,0,0,0,0],
        "Human-Computer Interaction":         [0,0,0,0,0,0,0,0,1,0,0,1],
        "Software Project Management":        [0,0,0,0,0,0,0,0,0,0,0,1],
        "Distributed Systems & Networking":   [1,0,1,0,0,0,1,0,0,1,0,0],
        "Mobile Application Development":     [1,0,0,0,0,0,0,1,1,0,0,0],
        "Machine Learning & AI":              [1,0,0,1,1,0,0,0,0,0,1,0],
        "Cloud Computing":                    [1,0,1,0,0,0,0,0,0,1,0,0],
        "SE Dissertation":                    [1,1,0,0,0,0,0,0,0,0,0,1],
    },
    "BSc Computer Science (Staffordshire)": {
        "Introduction to Programming":        [1,1,0,0,0,0,0,0,0,0,0,0],
        "Computer Architecture & Systems":    [1,0,1,0,0,0,0,0,0,0,0,0],
        "Mathematics for Computing":          [0,1,0,0,1,0,0,0,0,0,0,0],
        "Data Structures & Algorithms":       [1,1,0,0,0,0,0,0,0,0,0,0],
        "Database Systems":                   [0,0,0,0,0,1,0,0,0,0,0,0],
        "Web Development":                    [1,0,0,0,0,0,0,1,0,0,0,0],
        "Operating Systems & Networks":       [0,0,1,0,0,0,1,0,0,0,0,0],
        "Software Engineering":               [1,1,0,0,0,0,0,0,0,0,0,1],
        "Artificial Intelligence":            [1,0,0,1,1,0,0,0,0,0,1,0],
        "Cybersecurity":                      [0,0,1,0,0,0,1,0,0,0,0,0],
        "Blockchain & Emerging Tech":         [1,0,1,0,0,0,1,0,0,0,0,0],
        "Cloud & Big Data":                   [1,0,1,0,0,1,0,0,0,1,0,0],
        "CS Project":                         [1,1,0,0,0,0,0,0,0,0,0,1],
    },
    "BSc Computer Games Design (Staffordshire)": {
        "Game Programming Fundamentals":      [1,1,0,0,0,0,0,0,0,0,0,0],
        "Game Design Principles":             [0,0,0,0,0,0,0,0,1,0,0,1],
        "Mathematics for Games":              [0,1,0,0,1,0,0,0,0,0,0,0],
        "3D Graphics & Rendering":            [1,0,1,0,0,0,0,0,1,0,0,0],
        "Object-Oriented Programming":        [1,1,0,0,0,0,0,0,0,0,0,0],
        "AI for Games":                       [1,0,0,1,0,0,0,0,0,0,1,0],
        "Game Engine Development":            [1,1,1,0,0,0,0,0,0,0,0,0],
        "Network Games Programming":          [1,0,1,0,0,0,1,0,0,0,0,0],
        "UX & Interaction Design":            [0,0,0,0,0,0,0,0,1,0,0,1],
        "Games Project":                      [1,1,0,0,0,0,0,0,1,0,0,1],
    },
    "BA Games Art (Staffordshire)": {
        "2D Art & Concept Design":            [0,0,0,0,0,0,0,0,1,0,0,1],
        "3D Modelling":                       [0,0,0,0,0,0,0,0,1,0,0,0],
        "Character Design":                   [0,0,0,0,0,0,0,0,1,0,0,1],
        "Animation":                          [0,0,0,0,0,0,0,0,1,0,0,0],
        "Environment Art":                    [0,0,0,0,0,0,0,0,1,0,0,0],
        "Visual Effects":                     [0,0,0,0,0,0,0,0,1,0,0,0],
        "Art Production Pipeline":            [0,0,0,0,0,0,0,0,1,0,0,1],
        "Game Art Portfolio":                 [0,0,0,0,0,0,0,0,1,0,0,1],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. GOOGLE GRADUATE ROLES (based on real 2026 JDs)
# ─────────────────────────────────────────────────────────────────────────────
GOOGLE_ROLES = [
    {
        "name": "Software Engineer (Generalist)",
        "dept": "Engineering — L3 University Graduate",
        "vec":  [1,1,1,0,0,1,1,1,0,1,0,1],
        "must": ["Programming (Python/C++/Java)", "Algorithms & Data Structures"],
        "nice": ["Systems & Architecture", "Cloud & Distributed Systems"],
        "difficulty": "High",
        "desc": "Design, test, deploy software on Search, Ads, Android, Cloud, YouTube.",
        "tip":  "Practice 100+ LeetCode problems. Know Big-O, sorting, graphs, DP.",
    },
    {
        "name": "Software Engineer — AI/ML",
        "dept": "Google DeepMind / Gemini Products",
        "vec":  [1,1,0,1,1,1,0,0,0,1,1,1],
        "must": ["Machine Learning / AI", "Programming (Python/C++/Java)"],
        "nice": ["NLP / Computer Vision", "Data Analysis & Stats"],
        "difficulty": "Very High",
        "desc": "Build ML systems: data pipelines, model training, APIs with TensorFlow/PyTorch.",
        "tip":  "Andrew Ng ML Specialization + build end-to-end ML project on GitHub.",
    },
    {
        "name": "Data Scientist / Analyst",
        "dept": "Google Ads, Search, YouTube Analytics",
        "vec":  [1,1,0,1,1,1,0,0,0,1,0,1],
        "must": ["Data Analysis & Stats", "Databases & SQL"],
        "nice": ["Machine Learning / AI", "Programming (Python/C++/Java)"],
        "difficulty": "Medium-High",
        "desc": "Derive insights from massive datasets; build dashboards; influence product.",
        "tip":  "Master SQL, pandas, matplotlib. Enter Kaggle competitions.",
    },
    {
        "name": "UX Researcher",
        "dept": "Google Design",
        "vec":  [0,0,0,0,1,0,0,0,1,0,0,1],
        "must": ["UX & Product Design", "Soft Skills & Communication"],
        "nice": ["Data Analysis & Stats"],
        "difficulty": "Medium",
        "desc": "Conduct user research, usability testing, communicate insights to PMs.",
        "tip":  "Build a UX research portfolio with 2–3 case studies.",
    },
    {
        "name": "UX Designer",
        "dept": "Google Design",
        "vec":  [0,0,0,0,0,0,0,1,1,0,0,1],
        "must": ["UX & Product Design", "Web / Full-Stack Dev"],
        "nice": ["Soft Skills & Communication"],
        "difficulty": "Medium",
        "desc": "Design interfaces for Google products. Figma, prototyping, visual systems.",
        "tip":  "Google UX Design Certificate on Coursera + strong Figma portfolio.",
    },
    {
        "name": "Site Reliability Engineer (SRE)",
        "dept": "Google Infrastructure",
        "vec":  [1,1,1,0,1,1,1,0,0,1,0,1],
        "must": ["Systems & Architecture", "Networking & Security"],
        "nice": ["Cloud & Distributed Systems", "Programming (Python/C++/Java)"],
        "difficulty": "High",
        "desc": "Keep Google services running at scale. Linux, distributed systems, on-call ops.",
        "tip":  "Read Google's SRE Book (free online). Study Linux internals.",
    },
    {
        "name": "Security Engineer",
        "dept": "Google Trust & Safety / Chrome Security",
        "vec":  [1,1,1,0,0,1,1,0,0,1,0,1],
        "must": ["Networking & Security", "Programming (Python/C++/Java)"],
        "nice": ["Systems & Architecture", "Cloud & Distributed Systems"],
        "difficulty": "High",
        "desc": "Identify vulnerabilities, build secure systems, respond to threats.",
        "tip":  "CompTIA Security+ or Google Cybersecurity Certificate. Practice CTFs.",
    },
    {
        "name": "Technical Program Manager",
        "dept": "Google Cloud / Infrastructure",
        "vec":  [1,1,0,0,0,0,1,0,0,1,0,1],
        "must": ["Soft Skills & Communication", "Programming (Python/C++/Java)"],
        "nice": ["Cloud & Distributed Systems", "Systems & Architecture"],
        "difficulty": "Medium-High",
        "desc": "Coordinate complex tech programs across engineering teams.",
        "tip":  "Build leadership experience: lead student projects, hackathons, BUV clubs.",
    },
    {
        "name": "Android / Mobile Developer",
        "dept": "Google Android Platform",
        "vec":  [1,1,1,0,0,1,1,1,0,0,0,1],
        "must": ["Programming (Python/C++/Java)", "Web / Full-Stack Dev"],
        "nice": ["Systems & Architecture", "Algorithms & Data Structures"],
        "difficulty": "High",
        "desc": "Build Android OS features, apps, and platform APIs. Java/Kotlin.",
        "tip":  "Build and publish an Android app on Google Play Store.",
    },
    {
        "name": "Cloud Solutions Engineer",
        "dept": "Google Cloud (GCP)",
        "vec":  [1,1,1,0,1,1,1,0,0,1,0,1],
        "must": ["Cloud & Distributed Systems", "Systems & Architecture"],
        "nice": ["Databases & SQL", "Networking & Security"],
        "difficulty": "Medium-High",
        "desc": "Help customers architect and deploy solutions on GCP.",
        "tip":  "Get Google Associate Cloud Engineer certificate. Build a cloud project.",
    },
    {
        "name": "Engineering Analyst",
        "dept": "Google Ads / Trust & Safety",
        "vec":  [1,0,0,1,1,1,0,1,0,0,0,1],
        "must": ["Data Analysis & Stats", "Programming (Python/C++/Java)"],
        "nice": ["Machine Learning / AI", "Databases & SQL"],
        "difficulty": "Medium",
        "desc": "Analyse ad systems, user data, trust signals. SQL + Python + policy.",
        "tip":  "Good entry point. Focus on SQL + Python data analysis portfolio.",
    },
    {
        "name": "Game / Interactive Developer",
        "dept": "Google Play / ARCore / Stadia",
        "vec":  [1,1,1,1,0,0,0,1,1,0,1,1],
        "must": ["Programming (Python/C++/Java)", "UX & Product Design"],
        "nice": ["Machine Learning / AI", "NLP / Computer Vision"],
        "difficulty": "Medium",
        "desc": "Build interactive & game experiences on Google platforms. Unity, ARCore, WebGL.",
        "tip":  "Best fit for Computer Games graduates. Build an ARCore demo project.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# 4. CORE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def build_user_vector(selected_modules: list[str]) -> np.ndarray:
    """Sum skill vectors for the selected modules."""
    vec = np.zeros(len(SKILLS))
    for module in selected_modules:
        for prog_modules in PROGRAMMES.values():
            if module in prog_modules:
                vec += np.array(prog_modules[module], dtype=float)
                break
    return vec


def compute_fit_scores(user_vec: np.ndarray) -> list[dict]:
    """Compute match % for each Google role using cosine similarity."""
    norm_user = user_vec / (np.linalg.norm(user_vec) or 1)
    results = []
    for role in GOOGLE_ROLES:
        role_vec = np.array(role["vec"], dtype=float)
        norm_role = role_vec / (np.linalg.norm(role_vec) or 1)
        score = round(cosine_similarity(norm_user, norm_role) * 100)
        results.append({**role, "score": score})
    return sorted(results, key=lambda x: x["score"], reverse=True)


def skill_gap(user_vec: np.ndarray, role: dict) -> tuple[list, list]:
    """Return (have_skills, missing_skills) for a given role."""
    have, miss = [], []
    for skill_name in role["must"]:
        idx = SKILLS.index(skill_name)
        if user_vec[idx] > 0:
            have.append(skill_name)
        else:
            miss.append(skill_name)
    return have, miss


def fit_label(score: int) -> str:
    if score >= 70: return "Top Fit ★"
    if score >= 50: return "Good Fit"
    if score >= 30: return "Partial Fit"
    return "Stretch"


def score_color(score: int) -> str:
    if score >= 70: return Fore.GREEN
    if score >= 50: return Fore.CYAN
    if score >= 30: return Fore.YELLOW
    return Fore.RED


# ─────────────────────────────────────────────────────────────────────────────
# 5. MODULE SELECTION MENU
# ─────────────────────────────────────────────────────────────────────────────

def select_modules() -> list[str]:
    """Interactive CLI to select BUV modules."""
    all_modules = {}
    for prog, mods in PROGRAMMES.items():
        for m in mods:
            all_modules[m] = prog

    print(Fore.CYAN + Style.BRIGHT + "\n══════════════════════════════════════════════")
    print(Fore.CYAN + Style.BRIGHT +   "   BUV SoCIT MODULE SELECTOR")
    print(Fore.CYAN + Style.BRIGHT + "══════════════════════════════════════════════")

    selected = []
    prog_colors = {
        "BSc Data Science & AI (Stirling)":          Fore.BLUE,
        "BSc Software Engineering (Stirling)":       Fore.GREEN,
        "BSc Computer Science (Staffordshire)":      Fore.RED,
        "BSc Computer Games Design (Staffordshire)": Fore.YELLOW,
        "BA Games Art (Staffordshire)":              Fore.MAGENTA,
    }
    numbered = []
    for prog, mods in PROGRAMMES.items():
        color = prog_colors.get(prog, Fore.WHITE)
        print(f"\n{color + Style.BRIGHT}{prog}{Style.RESET_ALL}")
        for m in mods:
            numbered.append(m)
            print(f"  {Fore.WHITE}[{len(numbered):>2}]{Style.RESET_ALL} {m}")

    print(Fore.CYAN + "\n──────────────────────────────────────────────")
    print("Options:")
    print("  • Enter module numbers separated by commas  e.g.  1,3,5,12")
    print("  • Type  'all'  to select everything")
    print("  • Type  'ds'   for all Data Science & AI modules")
    print("  • Type  'se'   for all Software Engineering modules")
    print("  • Type  'cs'   for all Computer Science modules")
    print(Fore.CYAN + "──────────────────────────────────────────────")

    user_input = input(Fore.WHITE + Style.BRIGHT + "\nYour selection: ").strip().lower()

    if user_input == "all":
        selected = list(all_modules.keys())
    elif user_input == "ds":
        selected = list(PROGRAMMES["BSc Data Science & AI (Stirling)"].keys())
    elif user_input == "se":
        selected = list(PROGRAMMES["BSc Software Engineering (Stirling)"].keys())
    elif user_input == "cs":
        selected = list(PROGRAMMES["BSc Computer Science (Staffordshire)"].keys())
    else:
        try:
            indices = [int(x.strip()) - 1 for x in user_input.split(",")]
            selected = [numbered[i] for i in indices if 0 <= i < len(numbered)]
        except (ValueError, IndexError):
            print(Fore.RED + "Invalid input. Selecting all modules as default.")
            selected = list(all_modules.keys())

    return selected


# ─────────────────────────────────────────────────────────────────────────────
# 6. DISPLAY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def print_banner():
    print(Fore.BLUE + Style.BRIGHT + """
╔══════════════════════════════════════════════════════════════════════════╗
║   🌐  GOOGLE × BUV SoCIT — Graduate Career Fit Analyzer  🎓            ║
║   Based on real 2026 Google University Graduate job requirements        ║
╚══════════════════════════════════════════════════════════════════════════╝""")


def print_results_table(results: list[dict], user_vec: np.ndarray):
    print(Fore.CYAN + Style.BRIGHT + "\n══════════════════════════════════════════════════════════════════")
    print(Fore.CYAN + Style.BRIGHT +   "   GOOGLE ROLE FIT RANKING")
    print(Fore.CYAN + Style.BRIGHT + "══════════════════════════════════════════════════════════════════")

    rows = []
    for i, r in enumerate(results, 1):
        have, miss = skill_gap(user_vec, r)
        color = score_color(r["score"])
        rows.append([
            f"{i}",
            r["name"],
            r["dept"].split("—")[-1].strip() if "—" in r["dept"] else r["dept"],
            f"{color}{r['score']}%{Style.RESET_ALL}",
            f"{color}{fit_label(r['score'])}{Style.RESET_ALL}",
            r["difficulty"],
            ", ".join(miss) if miss else "✓ All covered",
        ])

    headers = ["#", "Google Role", "Team / Dept", "Match", "Fit", "Competition", "Missing Skills"]
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))


def print_top3_detail(results: list[dict], user_vec: np.ndarray):
    print(Fore.CYAN + Style.BRIGHT + "\n══════════════════════════════════════════════════════════════════")
    print(Fore.CYAN + Style.BRIGHT +   "   TOP 3 ROLE DEEP DIVES")
    print(Fore.CYAN + Style.BRIGHT + "══════════════════════════════════════════════════════════════════")

    for i, r in enumerate(results[:3], 1):
        color = score_color(r["score"])
        have, miss = skill_gap(user_vec, r)
        print(f"\n{color + Style.BRIGHT}#{i} {r['name']} — {r['score']}% match{Style.RESET_ALL}")
        print(f"   {Fore.WHITE}{r['dept']}{Style.RESET_ALL}")
        print(f"   {r['desc']}")
        print(f"   Competition: {Fore.YELLOW}{r['difficulty']}{Style.RESET_ALL}")
        if have:
            print(f"   {Fore.GREEN}✓ Skills covered: {', '.join(have)}{Style.RESET_ALL}")
        if miss:
            print(f"   {Fore.RED}✗ Must-have gaps: {', '.join(miss)}{Style.RESET_ALL}")
        print(f"   {Fore.CYAN}💡 Tip: {r['tip']}{Style.RESET_ALL}")


def print_skill_profile(user_vec: np.ndarray):
    print(Fore.CYAN + Style.BRIGHT + "\n══════════════════════════════════════════════════════════════════")
    print(Fore.CYAN + Style.BRIGHT +   "   YOUR SKILL PROFILE")
    print(Fore.CYAN + Style.BRIGHT + "══════════════════════════════════════════════════════════════════")
    max_val = max(user_vec) if max(user_vec) > 0 else 1
    for s, v in zip(SKILLS, user_vec):
        pct = int(v / max_val * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        color = Fore.GREEN if pct > 60 else Fore.YELLOW if pct > 30 else Fore.RED
        print(f"  {s:<36} {color}{bar}{Style.RESET_ALL} {pct:>3}%")


def print_roadmap(results: list[dict], user_vec: np.ndarray):
    top = results[0]
    print(Fore.CYAN + Style.BRIGHT + f"\n══════════════════════════════════════════════════════════════════")
    print(Fore.CYAN + Style.BRIGHT +   f"   ROADMAP TO: {top['name'].upper()}")
    print(Fore.CYAN + Style.BRIGHT + f"══════════════════════════════════════════════════════════════════")

    LEARNING_TIPS = {
        "Programming (Python/C++/Java)":    "LeetCode + CS50 Harvard (free). Aim for 100+ problems.",
        "Algorithms & Data Structures":     "Read 'Grokking Algorithms'. Practice arrays, trees, graphs on LeetCode.",
        "Systems & Architecture":           "'Operating Systems: Three Easy Pieces' (free PDF). Study Linux.",
        "Machine Learning / AI":            "Andrew Ng ML Specialization on Coursera + Kaggle competitions.",
        "Data Analysis & Stats":            "Khan Academy Statistics + Pandas/NumPy on real datasets.",
        "Databases & SQL":                  "Mode SQL Tutorial (free) + build a PostgreSQL project.",
        "Networking & Security":            "CompTIA Network+ or Google Cybersecurity Certificate on Coursera.",
        "Web / Full-Stack Dev":             "Build a React + Django/Node project and deploy it.",
        "UX & Product Design":              "Google UX Design Certificate + Figma portfolio case study.",
        "Cloud & Distributed Systems":      "Google Associate Cloud Engineer cert + build a GCP project.",
        "NLP / Computer Vision":            "Hugging Face NLP Course (free) + fast.ai vision course.",
        "Soft Skills & Communication":      "Join BUV debate/clubs, do mock interviews, present projects.",
    }

    all_miss = []
    for skill_name in top["must"] + top["nice"]:
        idx = SKILLS.index(skill_name)
        if user_vec[idx] == 0:
            all_miss.append(skill_name)

    if not all_miss:
        print(Fore.GREEN + f"\n  ✓ You cover all key skills for {top['name']}!")
        print(Fore.GREEN + "  Focus on building a strong project portfolio and practicing coding interviews.")
    else:
        print(f"\n  To maximise your fit for {Fore.YELLOW + top['name'] + Style.RESET_ALL}:\n")
        for step, skill_name in enumerate(all_miss, 1):
            print(f"  {Fore.BLUE}Step {step}{Style.RESET_ALL}: {Fore.WHITE + skill_name + Style.RESET_ALL}")
            print(f"          {LEARNING_TIPS.get(skill_name, 'Look for specialist resources.')}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 7. MATPLOTLIB VISUALISATIONS
# ─────────────────────────────────────────────────────────────────────────────

ROLE_COLORS = [
    "#4285F4","#34A853","#FBBC05","#EA4335","#9334E8",
    "#0F9D58","#DB4437","#FF6D00","#3DDC84","#1A73E8",
    "#F4511E","#D4537E",
]


def plot_bar_chart(results: list[dict]):
    """Horizontal bar chart of all Google role fit scores."""
    names = [r["name"] for r in results]
    scores = [r["score"] for r in results]
    colors = [ROLE_COLORS[i % len(ROLE_COLORS)] for i in range(len(results))]

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    bars = ax.barh(names[::-1], scores[::-1], color=colors[::-1], height=0.65, edgecolor="none")

    for bar, score in zip(bars, scores[::-1]):
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{score}%", va="center", ha="left", color="white", fontsize=9, fontweight="bold")

    ax.set_xlim(0, 105)
    ax.set_xlabel("Match Score (%)", color="white", fontsize=10)
    ax.set_title("🌐 Google Role Fit — BUV SoCIT Graduate", color="white", fontsize=13, fontweight="bold", pad=15)
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.axvline(50, color="white", linestyle="--", alpha=0.2, linewidth=1)
    ax.axvline(70, color="#34A853", linestyle="--", alpha=0.3, linewidth=1)
    ax.text(50.5, -0.8, "50%", color="white", alpha=0.4, fontsize=8)
    ax.text(70.5, -0.8, "70%", color="#34A853", alpha=0.5, fontsize=8)
    plt.tight_layout()
    plt.savefig("google_fit_bar.png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.show()
    print(Fore.GREEN + "  ✓ Bar chart saved as google_fit_bar.png")


def plot_radar_chart(results: list[dict], user_vec: np.ndarray):
    """Radar chart: your profile vs top 3 Google roles."""
    top3 = results[:3]
    categories = [s.split(" (")[0] for s in SKILLS]
    N = len(categories)
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]

    norm = np.linalg.norm(user_vec) or 1
    user_norm = (user_vec / norm * 3).tolist()
    user_norm += user_norm[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    ax.fill(angles, user_norm, color="#4285F4", alpha=0.15)
    ax.plot(angles, user_norm, color="#4285F4", linewidth=2, label="You")

    top_colors = ["#34A853","#FBBC05","#EA4335"]
    for role, color in zip(top3, top_colors):
        jn = np.linalg.norm(role["vec"]) or 1
        role_vals = (np.array(role["vec"], float) / jn * 3).tolist()
        role_vals += role_vals[:1]
        ax.plot(angles, role_vals, color=color, linewidth=1.5,
                linestyle="--", label=role["name"], alpha=0.8)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, color="white", size=8)
    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(["", "", ""], color="white")
    ax.grid(color="white", alpha=0.1)
    ax.spines["polar"].set_color("white")
    ax.spines["polar"].set_alpha(0.2)

    legend = ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.15),
                       facecolor="#16213e", edgecolor="white", labelcolor="white", fontsize=8)
    ax.set_title("Skill Radar — You vs Top Google Roles", color="white",
                 fontsize=12, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig("google_fit_radar.png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.show()
    print(Fore.GREEN + "  ✓ Radar chart saved as google_fit_radar.png")


def plot_skill_heatmap(results: list[dict], user_vec: np.ndarray):
    """Heatmap: skill coverage across all Google roles + your profile."""
    role_names = [r["name"].replace(" / ", "/").replace(" & ", "&")[:28] for r in results]
    matrix = np.array([r["vec"] for r in results], dtype=float)
    user_row = np.array([min(v, 1) for v in user_vec], dtype=float).reshape(1, -1)
    combined = np.vstack([user_row, matrix])
    row_labels = ["YOU"] + role_names

    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    im = ax.imshow(combined, cmap="YlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(SKILLS)))
    short = [s.split(" (")[0][:20] for s in SKILLS]
    ax.set_xticklabels(short, rotation=35, ha="right", color="white", fontsize=8)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, color="white", fontsize=8)

    for i in range(combined.shape[0]):
        for j in range(combined.shape[1]):
            val = combined[i, j]
            text_color = "black" if val > 0.5 else "white"
            ax.text(j, i, "●" if val > 0 else "", ha="center", va="center",
                    color=text_color, fontsize=10)

    ax.set_title("Skill Coverage Heatmap — You vs Every Google Role",
                 color="white", fontsize=12, fontweight="bold", pad=12)
    fig.colorbar(im, ax=ax, label="Skill weight", shrink=0.6).ax.yaxis.label.set_color("white")
    plt.tight_layout()
    plt.savefig("google_fit_heatmap.png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.show()
    print(Fore.GREEN + "  ✓ Heatmap saved as google_fit_heatmap.png")


# ─────────────────────────────────────────────────────────────────────────────
# 8. MAIN PROGRAM
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print_banner()

    # Step 1 – select modules
    selected_modules = select_modules()

    if not selected_modules:
        print(Fore.RED + "No modules selected. Exiting.")
        return

    print(Fore.GREEN + f"\n✓ {len(selected_modules)} module(s) selected.")

    # Step 2 – build vectors & compute scores
    user_vec = build_user_vector(selected_modules)
    results = compute_fit_scores(user_vec)

    # Step 3 – print summary stats
    covered = int(np.sum(user_vec > 0))
    top = results[0]
    print(Fore.WHITE + Style.BRIGHT + f"""
  ┌─────────────────────────────────────────┐
  │  Skill areas covered : {covered}/{len(SKILLS)}               │
  │  Best Google fit     : {top['name'][:28]:<28} │
  │  Best match score    : {top['score']}%                     │
  └─────────────────────────────────────────┘""")

    # Step 4 – full table
    print_results_table(results, user_vec)

    # Step 5 – top 3 deep dives
    print_top3_detail(results, user_vec)

    # Step 6 – skill profile
    print_skill_profile(user_vec)

    # Step 7 – roadmap
    print_roadmap(results, user_vec)

    # Step 8 – visualisations
    print(Fore.CYAN + Style.BRIGHT + "\n══════════════════════════════════════════════════════════════════")
    print(Fore.CYAN + Style.BRIGHT +   "   GENERATING CHARTS")
    print(Fore.CYAN + Style.BRIGHT + "══════════════════════════════════════════════════════════════════\n")
    plot_bar_chart(results)
    plot_radar_chart(results, user_vec)
    plot_skill_heatmap(results, user_vec)

    print(Fore.GREEN + Style.BRIGHT + "\n✓ Analysis complete! All charts saved in your working directory.\n")


if __name__ == "__main__":
    main()