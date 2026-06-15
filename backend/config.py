import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Allow DATA_DIR override via env (HuggingFace Spaces → /data)
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"

DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

_DATABASE_URL_ENV = os.environ.get("DATABASE_URL", "")
if _DATABASE_URL_ENV:
    DATABASE_PATH = None  # PostgreSQL — no local SQLite file
else:
    DATABASE_PATH = DATA_DIR / "joblin.db"

GENERATED_DIR = DATA_DIR / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_NVIDIA_KEY = os.environ.get("JOBLIN_OPENROUTER_KEY", "")

JWT_SECRET = os.environ.get("JOBLIN_JWT_SECRET", "joblin-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_TIMEOUT = 60000

# ── Search Queries — what Joblin scrapes automatically ────────────────────────
# Covers all major job types an average Nigerian professional looks for.
# Organised by sector so cron can rotate through them efficiently.

SEARCH_QUERIES = [
    # ── Data & Analytics ──────────────────────────────────────────────────────
    "Data Analyst", "Data Entry", "Database Administrator",
    "Business Intelligence Analyst", "Data Associate", "Data Officer",
    "Data Manager", "Data Engineer", "Data Scientist",

    # ── Project & Programme Management ────────────────────────────────────────
    "Project Manager", "Project Officer", "Programme Manager",
    "Programme Officer", "Project Coordinator", "Project Assistant",
    "Planning Officer", "Portfolio Manager",

    # ── Monitoring & Evaluation ───────────────────────────────────────────────
    "Monitoring and Evaluation", "M&E Officer", "MEAL Officer",
    "M&E Specialist", "Research and Evaluation", "Impact Analyst",

    # ── Finance & Accounting ──────────────────────────────────────────────────
    "Accountant", "Finance Officer", "Financial Analyst",
    "Budget Analyst", "Audit Officer", "Accounts Officer",
    "Treasury Officer", "Tax Consultant", "Cost Accountant",

    # ── Human Resources ───────────────────────────────────────────────────────
    "HR Officer", "Human Resources Manager", "Recruitment Officer",
    "Talent Acquisition", "HR Generalist", "Learning and Development",
    "Compensation and Benefits",

    # ── Administration & Operations ───────────────────────────────────────────
    "Administrative Officer", "Executive Assistant", "Office Manager",
    "Operations Manager", "Operations Officer", "Administrative Assistant",
    "Personal Assistant", "Secretary",

    # ── Customer Service & Support ────────────────────────────────────────────
    "Customer Service Officer", "Customer Experience", "Call Centre Agent",
    "Help Desk Officer", "Client Relations Officer", "Support Officer",

    # ── Sales & Business Development ──────────────────────────────────────────
    "Sales Executive", "Business Development Manager", "Sales Manager",
    "Sales Representative", "Account Manager", "Business Development Officer",
    "Commercial Manager",

    # ── Marketing & Communications ────────────────────────────────────────────
    "Marketing Officer", "Digital Marketing", "Communications Officer",
    "Content Writer", "Social Media Manager", "Brand Manager",
    "Public Relations Officer", "Media Officer",

    # ── Public Health & Medical ────────────────────────────────────────────────
    "Public Health Officer", "Health Programme Officer", "Community Health",
    "Epidemiologist", "Health Informatics", "Clinical Officer",
    "Pharmacist", "Laboratory Scientist",

    # ── NGO & International Development ──────────────────────────────────────
    "Programme Coordinator", "Field Officer", "Case Manager",
    "Humanitarian Officer", "WASH Officer", "Livelihoods Officer",
    "Protection Officer", "Grants Officer", "Donor Relations",

    # ── Engineering (Non-Software) ────────────────────────────────────────────
    "Civil Engineer", "Mechanical Engineer", "Electrical Engineer",
    "Structural Engineer", "Chemical Engineer", "Process Engineer",
    "Site Engineer", "HSE Officer", "Quality Control Officer",

    # ── IT & Software ─────────────────────────────────────────────────────────
    "Software Engineer", "Software Developer", "Systems Administrator",
    "Network Engineer", "IT Support", "Cybersecurity Analyst",
    "DevOps Engineer", "Full Stack Developer",

    # ── AI & Machine Learning ─────────────────────────────────────────────────
    "Machine Learning Engineer", "AI Engineer", "AI Data Analyst",

    # ── Procurement & Supply Chain ────────────────────────────────────────────
    "Procurement Officer", "Supply Chain Manager", "Logistics Officer",
    "Warehouse Manager", "Fleet Manager", "Store Keeper",

    # ── Legal & Compliance ────────────────────────────────────────────────────
    "Legal Officer", "Compliance Officer", "Company Secretary",
    "Corporate Lawyer", "Legal Counsel",

    # ── Graduate & Entry Level ────────────────────────────────────────────────
    "Graduate Trainee", "Management Trainee", "NYSC", "Intern",
    "Entry Level", "Fresh Graduate",
]

HIGHIMPACT_QUERIES = [
    "AI Program Manager", "AI Policy Analyst", "Digital Transformation",
    "AI for Good", "Nonprofit Technology", "Data for Good",
    "Machine Learning Engineer", "AI Ethics", "Program Manager",
    "Data Science Nonprofit", "Technology for Development",
]

JOB_BOARDS = {
    "nigeria": {
        "myjobmag": {
            "base_url": "https://www.myjobmag.com",
            "search_url": "https://www.myjobmag.com/search?q={query}",
            "type": "public", "region": "Nigeria", "icon": "ng", "enabled": True,
        },
        "jobberman": {
            "base_url": "https://www.jobberman.com",
            "search_url": "https://www.jobberman.com/jobs?q={query}",
            "type": "public", "region": "Nigeria", "icon": "ng", "enabled": True,
        },
        "jobgurus": {
            "base_url": "https://www.jobgurus.com.ng",
            "search_url": "https://www.jobgurus.com.ng/?s={query}",
            "type": "public", "region": "Nigeria", "icon": "ng", "enabled": True,
        },
        "hotnigerianjobs": {
            "base_url": "https://www.hotnigerianjobs.com",
            "search_url": "https://www.hotnigerianjobs.com/?s={query}",
            "type": "public", "region": "Nigeria", "icon": "ng", "enabled": True,
        },
        "ngcareers": {
            "base_url": "https://ngcareers.com",
            "search_url": "https://ngcareers.com/jobs?q={query}",
            "type": "public", "region": "Nigeria", "icon": "ng", "enabled": True,
        },
        "jobzilla": {
            "base_url": "https://www.jobzilla.ng",
            "search_url": "https://www.jobzilla.ng/jobs?q={query}",
            "type": "public", "region": "Nigeria", "icon": "ng", "enabled": True,
        },
        "smartyacad": {
            "base_url": "https://jobs.smartyacad.com",
            "search_url": "https://jobs.smartyacad.com/wp-json/wp/v2/posts?categories=10&per_page=50",
            "type": "public", "region": "Nigeria", "icon": "ng", "enabled": True,
        },
    },
    "ngo": {
        "myngojob": {
            "base_url": "https://www.myngojob.com",
            "search_url": "https://www.myngojob.com/search?q={query}",
            "type": "public", "region": "Nigeria/NGO", "icon": "ngo", "enabled": True,
        },
        "reliefweb": {
            "base_url": "https://reliefweb.int",
            "search_url": "https://reliefweb.int/jobs?search={query}",
            "type": "public", "region": "Global/NGO", "icon": "ngo", "enabled": True,
        },
        "devex": {
            "base_url": "https://www.devex.com",
            "search_url": "https://www.devex.com/jobs/search?keywords={query}",
            "type": "public", "region": "Global/Development", "icon": "ngo", "enabled": True,
        },
        "impactpool": {
            "base_url": "https://www.impactpool.org",
            "search_url": "https://www.impactpool.org/search?q={query}",
            "type": "public", "region": "Global/NGO", "icon": "ngo", "enabled": True,
        },
        "idealist": {
            "base_url": "https://www.idealist.org",
            "search_url": "https://www.idealist.org/en/jobs?q={query}",
            "type": "public", "region": "Global/Nonprofit", "icon": "ngo", "enabled": True,
        },
        "unicef": {
            "base_url": "https://jobs.unicef.org",
            "search_url": "https://jobs.unicef.org/en-us/search?searchbykeyword={query}",
            "type": "public", "region": "Global/UN", "icon": "ngo", "enabled": True,
        },
        "who": {
            "base_url": "https://careers.who.int",
            "search_url": "https://careers.who.int/search?q={query}",
            "type": "public", "region": "Global/UN", "icon": "ngo", "enabled": True,
        },
        "devnetjobs": {
            "base_url": "https://www.devnetjobs.org",
            "search_url": "",
            "type": "login_required", "region": "Global/Development", "icon": "ngo", "enabled": True,
        },
        "irc": {
            "base_url": "https://rescue.csod.com",
            "search_url": "https://rescue.csod.com/ux/ats/careersite/1/home?q={query}",
            "type": "public", "region": "Global/NGO", "icon": "ngo", "enabled": True,
        },
    },
    "international": {
        "indeed": {
            "base_url": "https://www.indeed.com",
            "search_url": "https://www.indeed.com/jobs?q={query}&fromage=7",
            "type": "playwright", "region": "USA/Global", "icon": "global", "enabled": True,
        },
        "glassdoor": {
            "base_url": "https://www.glassdoor.com",
            "search_url": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}",
            "type": "login_optional", "region": "USA/Global", "icon": "global", "enabled": True,
        },
        "linkedin": {
            "base_url": "https://www.linkedin.com",
            "search_url": "https://www.linkedin.com/jobs/search/?keywords={query}&f_TPR=r604800",
            "type": "login_required", "region": "Global", "icon": "global", "enabled": True,
        },
        "reed": {
            "base_url": "https://www.reed.co.uk",
            "search_url": "https://www.reed.co.uk/jobs?keywords={query}&sortby=DisplayDate",
            "type": "public", "region": "UK", "icon": "global", "enabled": True,
        },
        "adzuna": {
            "base_url": "https://www.adzuna.co.uk",
            "search_url": "https://www.adzuna.co.uk/search?q={query}",
            "type": "public", "region": "UK", "icon": "global", "enabled": True,
        },
        "remoteok": {
            "base_url": "https://remoteok.com",
            "search_url": "https://remoteok.com/api?tag={query}",
            "type": "public", "region": "Remote/Global", "icon": "global", "enabled": True,
        },
        "cwjobs": {
            "base_url": "https://www.cwjobs.co.uk",
            "search_url": "https://www.cwjobs.co.uk/jobs?q={query}",
            "type": "public", "region": "UK Tech", "icon": "global", "enabled": True,
        },
        "eurojobs": {
            "base_url": "https://www.eurojobs.com",
            "search_url": "https://www.eurojobs.com/jobs/?keywords={query}",
            "type": "public", "region": "Europe", "icon": "global", "enabled": True,
        },
        "letsworkremotely": {
            "base_url": "https://letsworkremotely.com",
            "search_url": "https://letsworkremotely.com/remote-jobs/?search={query}",
            "type": "public", "region": "Remote/Global", "icon": "global", "enabled": True,
        },
        "realworkfromanywhere": {
            "base_url": "https://realworkfromanywhere.com",
            "search_url": "https://realworkfromanywhere.com/",
            "type": "public", "region": "Remote/Global", "icon": "global", "enabled": True,
        },
        "himalayas": {
            "base_url": "https://himalayas.app",
            "search_url": "https://himalayas.app/jobs/api?q={query}",
            "type": "public", "region": "Remote/Global", "icon": "global", "enabled": True,
        },
        "weworkremotely": {
            "base_url": "https://weworkremotely.com",
            "search_url": "https://weworkremotely.com/remote-jobs/search?term={query}",
            "type": "public", "region": "Remote/Global", "icon": "global", "enabled": True,
        },
        "remotive": {
            "base_url": "https://remotive.com",
            "search_url": "https://remotive.io/api/remote-jobs?search={query}",
            "type": "public", "region": "Remote/Global", "icon": "global", "enabled": True,
        },
        "remoteworkng": {
            "base_url": "https://remotework.ng",
            "search_url": "https://remotework.ng/?s={query}",
            "type": "public", "region": "Africa/Remote", "icon": "global", "enabled": True,
        },
    },
}

# ── Cron query subset (representative queries, not all 133)
# Boards return mostly the same results regardless of query via text heuristic.
# Using all 133 queries × 29 boards = 3,857 requests (takes 30+ min).
CRON_QUERIES = [
    "Data Analyst", "Project Manager", "Software Engineer",
]

JOB_BOARDS["highimpact"] = {
    "idealist": {
        "base_url": "https://www.idealist.org",
        "search_url": "https://www.idealist.org/en/jobs?q={query}",
        "type": "public", "region": "Global/Nonprofit", "icon": "ai", "enabled": True,
    },
    "80000hours": {
        "base_url": "https://80000hours.org",
        "search_url": "https://80000hours.org/job-board/?search={query}",
        "type": "public", "region": "Global/High-Impact", "icon": "ai", "enabled": True,
    },
    "anthropic": {
        "base_url": "https://www.anthropic.com",
        "search_url": "https://www.anthropic.com/careers?query={query}",
        "type": "public", "region": "Global/AI", "icon": "ai", "enabled": True,
    },
}

PUBLIC_BOARDS = []
PLAYWRIGHT_BOARDS = []
LOGIN_REQUIRED_BOARDS = []
LOGIN_OPTIONAL_BOARDS = []

for cat, boards in JOB_BOARDS.items():
    for name, cfg in boards.items():
        entry = (cat, name, cfg)
        t = cfg.get("type", "public")
        if t == "login_required":
            LOGIN_REQUIRED_BOARDS.append(entry)
        elif t == "login_optional":
            LOGIN_OPTIONAL_BOARDS.append(entry)
        elif t == "playwright":
            PLAYWRIGHT_BOARDS.append(entry)
        else:
            PUBLIC_BOARDS.append(entry)

# ── Job Category Taxonomy ───────────────────────────────────────────────────
JOB_CATEGORIES = {
    "project-management": {
        "name": "Project Management", "icon": "briefcase",
        "keywords": ["project manager","project officer","programme manager","programme officer",
                      "project coordinator","project assistant","planning officer","project lead",
                      "project director","programme coordinator","portfolio manager",
                      "project management","pmo","project administrator","planning manager",
                      "delivery manager","delivery lead","program manager","program officer",
                      "scrum master","agile coach","product owner","product manager",
                      "manager"],
        "color": "#0f766e",
    },
    "data-analytics": {
        "name": "Data & Analytics", "icon": "chart",
        "keywords": ["data analyst","data analytics","data entry","database administrator",
                      "database engineer","database developer","database architect",
                      "product analyst","marketing analyst","business analyst",
                      "dashboard developer","bi analyst","business intelligence","data associate",
                      "data engineer","data scientist","data architect","analytics manager",
                      "data manager","data officer","data clerk","business analyst",
                      "reporting analyst","insights analyst","data",
                      "analyst","analytics","actuarial","market analyst",
                      "research analyst","operations analyst","pricing analyst",
                      "risk analyst","credit analyst","investment analyst",
                      "data annotation","data labeling","data labeler","annotation analyst",
                      "ai training data","data curator","data quality analyst"],
        "color": "#059669",
    },
    "monitoring-evaluation": {
        "name": "Monitoring & Evaluation", "icon": "clipboard",
        "keywords": ["monitoring","evaluation","m&e","meal","me officer","mea officer",
                      "monitoring officer","evaluation officer","programme officer",
                      "program officer","impact assessment","results measurement",
                      "learning and evaluation","research and evaluation","impact analyst",
                      "knowledge management","reporting officer","data quality"],
        "color": "#0284c7",
    },
    "finance-accounting": {
        "name": "Finance & Accounting", "icon": "wallet",
        "keywords": ["accountant","finance officer","financial analyst","budget analyst",
                      "audit","accounts officer","treasury","tax consultant","cost accountant",
                      "finance manager","chief accountant","internal audit","financial controller",
                      "accounts payable","accounts receivable","bookkeeper","payroll",
                      "finance","accounting","accounts","tax","auditor","finance associate"],
        "color": "#9333ea",
    },
    "human-resources": {
        "name": "Human Resources", "icon": "users",
        "keywords": ["hr officer","human resources","recruitment officer","talent acquisition",
                      "hr generalist","learning and development","compensation","hr manager",
                      "people operations","hr business partner","employee relations",
                      "workforce planning","hr coordinator","recruiter",
                      "hr","human resource","talent","people manager","hr assistant",
                      "benefits","recruitment","staffing"],
        "color": "#db2777",
    },
    "admin-operations": {
        "name": "Admin & Operations", "icon": "settings",
        "keywords": ["administrative officer","executive assistant","office manager",
                      "operations manager","operations officer","administrative assistant",
                      "personal assistant","secretary","receptionist","admin officer",
                      "facilities manager","office administrator","operations coordinator",
                      "operations","facility","facilities","executive director",
                      "administrative","admin","supervisor","administration"],
        "color": "#64748b",
    },
    "customer-service": {
        "name": "Customer Service", "icon": "headphones",
        "keywords": ["customer service","customer experience","call centre","call center",
                      "help desk","client relations","support officer","customer support",
                      "customer success","client service","customer care","service desk",
                      "customer relations","client support",
                      "customer","helpdesk","support","client service"],
        "color": "#f59e0b",
    },
    "sales-marketing": {
        "name": "Sales & Marketing", "icon": "trending-up",
        "keywords": ["sales executive","business development","sales manager","sales representative",
                      "account manager","marketing officer","digital marketing","social media",
                      "social media manager","content writer","brand manager","public relations","communications officer",
                      "marketing analyst","marketing manager","market research",
                      "growth manager","seo","media officer","copywriter","advertising",
                      "marketing","sales","business development","account executive",
                      "brand","communications","content","growth","market",
                      "commercial","business development manager","brand specialist"],
        "color": "#ea580c",
    },
    "engineering": {
        "name": "Engineering", "icon": "tool",
        "keywords": ["civil engineer","mechanical engineer","electrical engineer",
                      "structural engineer","chemical engineer","process engineer",
                      "site engineer","hse officer","quality control","production engineer",
                      "maintenance engineer","instrumentation","petroleum engineer",
                      "field engineer","project engineer","safety officer","qhse",
                      "engineer","engineering","technician","maintenance","factory",
                      "technical officer","quality assurance","qa ","qc ",
                      "production","manufacturing","plant"],
        "color": "#b45309",
    },
    "software-dev": {
        "name": "Software & IT", "icon": "code",
        "keywords": ["software engineer","software developer","full-stack","backend",
                      "frontend","web developer","react","node.js","python developer",
                      "java developer","devops","mobile developer","systems administrator",
                      "network engineer","it support","cybersecurity","it officer","it manager",
                      "flutter","cloud engineer","database administrator",
                      "database engineer","database developer","database architect",
                      "software","developer","programmer","salesforce","aws","cloud",
                      "java","kotlin","microservice","api","sql","dba",
                      "tech lead","application","programmer analyst","it",
                      "database","data warehouse","etl","data pipeline"],
        "color": "#dc2626",
    },
    "ai-machine-learning": {
        "name": "AI & Machine Learning", "icon": "brain",
        "keywords": ["ai","artificial intelligence","machine learning","deep learning",
                      "llm","langchain","prompt engineer","ai engineer","ml engineer",
                      "ai researcher","ai developer","nlp","generative ai",
                      "data scientist","computer vision","neural network",
                      "chatbot","llm","gen ai","ai architect",
                      "automation","rpa","robotic process","workflow automation",
                      "process automation","ai automation","intelligent automation",
                      "automation engineer","automation specialist"],
        "color": "#7c3aed",
    },
    "public-health": {
        "name": "Public Health & Medical", "icon": "heart",
        "keywords": ["public health","epidemiologist","health informatics","health data",
                      "global health","community health","health information","health analyst",
                      "health officer","nutrition","wash","pharmacist","laboratory scientist",
                      "clinical officer","health program","medical officer","doctor","nurse",
                      "ncd","hiv","malaria","health coordinator",
                      "drug","pharma","clinical","medical","health"],
        "color": "#e11d48",
    },
    "ngo-development": {
        "name": "NGO & Development", "icon": "globe",
        "keywords": ["ngo","nonprofit","international development","humanitarian","donor",
                      "unicef","who","world bank","usaid","field officer","case manager",
                      "livelihoods","protection officer","grants officer","wash officer",
                      "development officer","relief","emergency","humanitarian assistance",
                      "non profit","human rights","advocacy","community development",
                      "program officer","program manager","project officer"],
        "color": "#2563eb",
    },
    "procurement-supply": {
        "name": "Procurement & Supply Chain", "icon": "package",
        "keywords": ["procurement officer","supply chain","logistics officer","warehouse manager",
                      "fleet manager","store keeper","purchasing","procurement manager",
                      "supply officer","inventory","distribution","transport officer",
                      "logistics manager","procurement specialist",
                      "procurement analyst","supply chain analyst","logistics analyst",
                      "procurement","logistics","supply","warehouse","inventory"],
        "color": "#0891b2",
    },
    "legal-compliance": {
        "name": "Legal & Compliance", "icon": "shield",
        "keywords": ["legal officer","compliance officer","company secretary","corporate lawyer",
                      "legal counsel","solicitor","barrister","paralegal","legal assistant",
                      "risk officer","regulatory","corporate governance","legal manager",
                      "legal","compliance","regulatory","attorney","lawyer",
                      "risk management","corporate secretarial",
                      "security","safety officer","security manager"],
        "color": "#475569",
    },
    "graduate-entry": {
        "name": "Graduate / Entry Level", "icon": "graduation-cap",
        "keywords": ["graduate trainee","management trainee","graduate","entry level",
                      "entry-level","junior","intern","trainee","recent graduate",
                      "nysc","fresh graduate","no experience","associate",
                      "graduate intern","graduate programme","young professional"],
        "color": "#d97706",
    },
    "remote": {
        "name": "Remote / Anywhere", "icon": "wifi",
        "keywords": ["remote","work from home","telecommute","virtual","distributed",
                      "anywhere","global","home based","home-based","fully remote",
                      "remote-first","remote first","work anywhere"],
        "color": "#0891b2",
    },
    "design-creative": {
        "name": "Design & Creative", "icon": "pen-tool",
        "keywords": ["graphic designer","graphic design","ui designer","ux designer",
                      "ui/ux","ui ux","product designer","visual designer","motion designer",
                      "motion graphics","video editor","video editing","animation",
                      "illustrator","illustration","brand designer","creative director",
                      "art director","creative designer","web designer","figma",
                      "photoshop","adobe","canva","designer","design",
                      "ux research","ux researcher","interaction design",
                      "multimedia","visual design","creative","artist"],
        "color": "#8b5cf6",
    },
    "content-writing": {
        "name": "Content & Writing", "icon": "edit",
        "keywords": ["content writer","content writing","copywriter","copywriting",
                      "technical writer","technical writing","editor","proofreader",
                      "content strategist","content manager","seo writer","ghostwriter",
                      "blog writer","medical writer","grant writer","proposal writer",
                      "writer","editorial","content creator","content developer",
                      "script writer","speech writer","news writer","journalist"],
        "color": "#ec4899",
    },
    "other": {
        "name": "Other", "icon": "grid",
        "keywords": [],
        "color": "#94a3b8",
    },
}
