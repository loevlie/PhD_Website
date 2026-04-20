"""
All portfolio content as Python data structures.
No database needed — academic portfolios change rarely.
"""

HERO = {
    'name': 'Dennis Johan Loevlie',
    'title': 'ELLIS PhD Student',
    'affiliation': 'CWI & University of Amsterdam',
    'bio': (
        'I am an ⭐ <a href="https://ellis.eu/research/phd-postdoc" target="_blank">ELLIS</a> PhD student at the <a href="https://www.cwi.nl/" target="_blank">Centrum Wiskunde & Informatica (CWI)</a> '
        'and the <a href="https://www.uva.nl/" target="_blank">University of Amsterdam</a>, '
        'working in the <a href="https://trl-lab.github.io/" target="_blank">Table Representation Learning Lab (TRLab)</a> '
        'and the <a href="https://amlab.science.uva.nl/" target="_blank">Amsterdam Machine Learning Lab (AMLab)</a>. '
        'I am advised by <a href="https://madelonhulsebos.github.io/" target="_blank">Madelon Hulsebos</a> '
        '(TRLab, CWI) and co-advised by <a href="https://jwvdm.github.io/" target="_blank">Jan-Willem van de Meent</a> '
        '(AMLab, UvA). '
        'My research focuses on <strong>tabular foundation models</strong>.'
    ),
    'bio_continued': (
        'Previously, I completed my M.S. in Computer Science at '
        '<a href="https://www.tufts.edu/" target="_blank">Tufts University</a>, '
        'where I was advised by '
        '<a href="https://www.michaelchughes.com/" target="_blank">Michael Hughes</a> '
        'on deep multiple instance learning for brain scan (CT and MRI) classification. '
        'I also hold an M.S. in Chemical Engineering from '
        '<a href="https://www.cmu.edu/" target="_blank">Carnegie Mellon University</a> '
        'and a B.S. in Chemical Engineering from '
        '<a href="https://www.wvu.edu/" target="_blank">West Virginia University</a>.'
    ),
    'profile_image': 'portfolio/images/me_in_nola.jpeg',
    'interests': [
        'Generative AI',
        'Multimodal Foundation Models',
        'Tabular Representation Learning',
        'Data-Efficient Learning',
    ],
}

NEWS = [
    {
        'date': '2026',
        'text': (
            'Won <strong>1st place</strong> out of 10 teams in the BrainStorm Neural Decoder Challenge &mdash; '
            'real-time auditory decoding from 1024-channel ECoG with 95% accuracy and sub-ms inference. '
            '<a href="https://qsimeon.github.io/brainstorm_bci_blog.html" target="_blank">Read our blog post &rarr;</a>'
        ),
        'highlight': True,
    },
    {
        'date': '2026',
        'text': (
            'Starting as an ELLIS PhD student at '
            '<a href="https://www.cwi.nl/" target="_blank">CWI</a> & '
            '<a href="https://www.uva.nl/" target="_blank">University of Amsterdam</a> in the '
            '<a href="https://trl-lab.github.io/" target="_blank">Table Representation Learning Lab</a>!'
        ),
        'highlight': True,
    },
    {
        'date': '2025',
        'text': (
            'Our paper "Synthetic Data Reveals Generalization Gaps in Correlated Multiple Instance Learning" '
            'accepted at <a href="https://ml4h.cc/2025/" target="_blank">ML4H 2025</a> Findings Track! '
            'Poster presentation in San Diego, December 2025.'
        ),
        'highlight': False,
    },
    {
        'date': '2024',
        'text': (
            'Awarded <strong>Community Grant</strong> from Hugging Face to demonstrate '
            '<a href="https://huggingface.co/spaces/JohanDL/Depth-Anything-Video" target="_blank">Depth Anything</a> '
            'results on videos.'
        ),
        'highlight': False,
    },
]

PUBLICATIONS = [
    {
        'type': 'conference',
        'title': 'Synthetic Data Reveals Generalization Gaps in Correlated Multiple Instance Learning',
        'authors': ['Ethan Harvey', 'Dennis Johan Loevlie', 'Michael C. Hughes'],
        'venue': 'ML4H 2025 Symposium, Findings Track',
        'year': 2025,
        'selected': True,
        'image': 'portfolio/images/mil_bayes.png',
        'links': [
            {'label': 'Paper', 'url': 'https://arxiv.org/abs/2510.25759'},
            {'label': 'Code', 'url': 'https://github.com/Franblueee/torchmil'},
        ],
        'bibtex': """@inproceedings{harvey2025synthetic,
  title={Synthetic Data Reveals Generalization Gaps in Correlated Multiple Instance Learning},
  author={Harvey, Ethan and Loevlie, Dennis Johan and Hughes, Michael C.},
  booktitle={ML4H 2025 Symposium, Findings Track},
  year={2025},
  url={https://arxiv.org/abs/2510.25759}
}""",
    },
    {
        'type': 'journal',
        'title': 'Demystifying the Chemical Ordering of Multimetallic Nanoparticles',
        'authors': ['Dennis Johan Loevlie', 'Brenno Ferreira', 'Giannis Mpourmpakis'],
        'venue': 'Accounts of Chemical Research',
        'year': 2023,
        'selected': True,
        'image': 'portfolio/images/cover_acr.jpeg',
        'image_credit': 'Cover art by Sungil Hong & Dennis Loevlie',
        'links': [
            {'label': 'Paper', 'url': 'https://doi.org/10.1021/acs.accounts.2c00646'},
            {'label': 'Code', 'url': 'https://github.com/mpourmpakis/CANELa_NP'},
        ],
        'bibtex': """@article{loevlie2023demystifying,
  title={Demystifying the Chemical Ordering of Multimetallic Nanoparticles},
  author={Loevlie, Dennis Johan and Ferreira, Brenno and Mpourmpakis, Giannis},
  journal={Accounts of Chemical Research},
  year={2023},
  doi={10.1021/acs.accounts.2c00646}
}""",
    },
    {
        'type': 'journal',
        'title': 'Single Atom Alloys Segregation in the Presence of Ligands',
        'authors': ['Maya Salem', 'Dennis J. Loevlie', 'Giannis Mpourmpakis'],
        'venue': 'The Journal of Physical Chemistry C',
        'year': 2023,
        'links': [
            {'label': 'Paper', 'url': 'https://doi.org/10.1021/acs.jpcc.3c05827'},
        ],
    },
    {
        'type': 'journal',
        'title': 'Size-Dependent Shape Distributions of Platinum Nanoparticles',
        'authors': ['Ruikang Ding', 'Ingrid M. Padilla Espinosa', 'Dennis Loevlie', 'Soodabeh Azadehranjbar', 'Andrew J. Baker', 'Giannis Mpourmpakis', 'Ashlie Martini', 'Tevis D. B. Jacobs'],
        'venue': 'Nanoscale Advances',
        'year': 2022,
        'links': [
            {'label': 'Paper', 'url': 'https://doi.org/10.1039/D2NA00326K'},
        ],
    },
    {
        'type': 'journal',
        'title': 'Resolving Electrocatalytic Imprecision in Atomically Precise Metal Nanoclusters',
        'authors': ['Anantha V. Nagarajan', 'Dennis Johan Loevlie', 'Michael J. Cowan', 'Giannis Mpourmpakis'],
        'venue': 'Current Opinion in Chemical Engineering',
        'year': 2022,
        'links': [
            {'label': 'Paper', 'url': 'https://doi.org/10.1016/j.coelec.2021.100860'},
        ],
    },
    {
        'type': 'poster',
        'title': 'Software Development for HER High-Throughput Experiments',
        'authors': ['Dennis Loevlie'],
        'venue': 'CMU ChemE Masters Student Association Research Forum',
        'year': 2020,
        'links': [
            {'label': 'Poster', 'url': 'https://www.loevliedl.com/static/Portfolio/PDF/CMU_Research_Poster.pdf'},
        ],
    },
    {
        'type': 'poster',
        'title': 'Mathematical Modeling and Optimization of an Ion Transport Membrane for Oxygen Separation from Air',
        'authors': ['Dennis Loevlie'],
        'venue': 'AIChE National Conference',
        'year': 2018,
        'links': [
            {'label': 'Poster', 'url': 'https://www.loevliedl.com/static/Portfolio/PDF/WVU_poster_Loevlie.pdf'},
        ],
    },
]

PROJECTS = [
    {
        'title': 'NeurOpt',
        'description': 'LLM-guided machine learning optimization tool that automates hyperparameter tuning and neural architecture search by analyzing training curves to propose experiments.',
        'tags': ['LLM', 'Optimization', 'PyTorch'],
        'github': 'loevlie/neuropt',
        'language': 'Python',
        'featured': True,
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/neuropt'},
        ],
    },
    {
        'title': 'GPT4Readability',
        'description': 'CLI tool leveraging LLMs and vector databases with LangChain and llama.cpp to generate README files and suggest code improvements. Supports cloud and local open-source LLMs across 15 languages.',
        'tags': ['NLP', 'LangChain', 'Open Source'],
        'github': 'loevlie/GPT4Readability',
        'language': 'Python',
        'featured': True,
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/GPT4Readability'},
            {'label': 'Demo', 'url': 'https://huggingface.co/spaces/JohanDL/GPT4Readability'},
        ],
    },
    {
        'title': 'SkinsAI',
        'description': 'Free diagnosis tool classifying moles as benign or malignant using a PyTorch CNN. Won 2nd place out of 24 teams at The Pitt Challenge Hackathon.',
        'tags': ['Medical AI', 'PyTorch', 'Hackathon'],
        'github': 'loevlie/SkinsAI',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/SkinsAI'},
            {'label': 'Competition', 'url': 'https://pittchallenge.com'},
            {'label': 'Devpost', 'url': 'https://devpost.com/software/skinsai'},
        ],
    },
    {
        'title': 'nb_search',
        'description': 'Search tool for finding content across Jupyter notebooks in a repository.',
        'tags': ['Developer Tools', 'Jupyter', 'Search'],
        'github': 'loevlie/nb_search',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/nb_search'},
            {'label': 'PyPI', 'url': 'https://pypi.org/project/nb-search/'},
        ],
    },
    {
        'title': 'Disparity Maps',
        'description': 'Stereo vision disparity map generation for depth perception from image pairs.',
        'tags': ['Computer Vision', 'Stereo', 'Depth'],
        'github': 'loevlie/DL_Project_PSMNet',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/DL_Project_PSMNet'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
            {'label': 'PDF', 'url': 'https://www.loevliedl.com/static/Portfolio/PDF/DL_Final.pdf'},
        ],
    },
    {
        'title': 'ASL Active Learning',
        'description': 'Active learning framework for American Sign Language recognition with efficient labeling.',
        'tags': ['Active Learning', 'Computer Vision', 'ASL'],
        'github': 'loevlie/ASL_Active_Learning',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/ASL_Active_Learning'},
        ],
    },
    {
        'title': 'Face Verification',
        'description': 'Face verification system using deep metric learning and siamese networks.',
        'tags': ['Computer Vision', 'Biometrics', 'Deep Learning'],
        'github': 'loevlie/Face_Verification',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Face_Verification'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
        ],
    },
    {
        'title': 'Rhine Water Level Prediction',
        'description': 'Time series forecasting for Rhine river water levels using ML models.',
        'tags': ['Time Series', 'Forecasting', 'Environmental'],
        'github': 'loevlie/Rhine_Water_Level_Prediction',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Rhine_Water_Level_Prediction'},
        ],
    },
    {
        'title': 'Speech Recognition',
        'description': 'Automatic speech recognition system using deep learning architectures.',
        'tags': ['Speech', 'Deep Learning', 'Audio'],
        'github': 'loevlie/Speech_Recognition',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Speech_Recognition'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
        ],
    },
    {
        'title': 'Speech to Text',
        'description': 'End-to-end speech-to-text transcription pipeline with attention mechanisms.',
        'tags': ['Speech', 'NLP', 'Seq2Seq'],
        'github': 'loevlie/Speech_to_Text_Transcription',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Speech_to_Text_Transcription'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
        ],
    },
    {
        'title': 'ML Codes',
        'description': 'Collection of machine learning algorithm implementations from scratch.',
        'tags': ['ML', 'Algorithms', 'Education'],
        'github': 'loevlie/ML_Codes',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/ML_Codes'},
            {'label': 'Course', 'url': 'http://www.cs.cmu.edu/~mgormley/courses/10601/'},
        ],
    },
    {
        'title': 'Patient Stay Prediction',
        'description': 'Predicting patient length of stay in hospitals using clinical data and ML.',
        'tags': ['Healthcare', 'ML', 'Prediction'],
        'github': 'loevlie/Pitt-Hackathon',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Pitt-Hackathon'},
            {'label': 'Slides', 'url': 'https://docs.google.com/presentation/d/1I-Sl-MyEbZGwBV4Ytol2Y7GEi3kSyOyh1Y8aRKm0H8s/edit?usp=sharing'},
        ],
    },
    {
        'title': 'QA Model',
        'description': 'Question answering system built with transformer-based architectures.',
        'tags': ['NLP', 'Transformers', 'QA'],
        'github': 'loevlie/Question_Answer_Model',
        'language': 'Python',
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Question_Answer_Model'},
        ],
    },
]

TIMELINE = [
    {
        'year': '2026 —',
        'title': 'ELLIS PhD Student',
        'org': 'CWI & University of Amsterdam',
        'description': 'Researching tabular foundation models. Advised by Madelon Hulsebos (TRLab, CWI) and co-advised by Jan-Willem van de Meent (AMLab, UvA).',
    },
    {
        'year': '2025',
        'title': 'Multimodal AI Intern',
        'org': 'ContentsPal',
        'description': 'MIT professor-led AI startup in the insurance space. Implemented learning-based duplicate detection and open-vocabulary instance segmentation.',
    },
    {
        'year': '2024 —',
        'title': 'M.S. Computer Science',
        'org': 'Tufts University',
        'description': 'GPA: 3.95. Research on deep MIL for brain scan (CT and MRI) classification with Dr. Michael Hughes. Also working with Dr. Jivko Sinapov on vision-language models and reinforcement learning.',
    },
    {
        'year': '2023 — 2024',
        'title': 'Senior CV & ML Engineer',
        'org': 'KEF Robotics',
        'description': 'Led a team of five engineers on a $500K NAMC project. Developed on-device object detection, monocular depth prediction, and 3D map generation for autonomous UAVs.',
        'link': 'https://www.cheme.engineering.cmu.edu/news/2024/07/10-alum-spotlight-loevlie.html',
        'link_label': 'CMU Spotlight',
    },
    {
        'year': '2021 — 2023',
        'title': 'Graduate Research Assistant',
        'org': 'University of Pittsburgh — CANELa Lab',
        'description': 'Applied ML, Boltzmann statistics, and evolutionary optimization to predict material properties of metal nanoparticles with Dr. Giannis Mpourmpakis.',
    },
    {
        'year': '2020 — 2021',
        'title': 'Lead Data Scientist',
        'org': 'AiThElite',
        'description': 'Pittsburgh-based startup using AI to improve the college athlete transfer process. Built the frontend and backend with Django, hosted on AWS.',
    },
    {
        'year': '2019 — 2020',
        'title': 'M.S. Chemical Engineering',
        'org': 'Carnegie Mellon University',
        'description': 'GPA: 3.91. Research with Dr. John Kitchin on software tools for high-throughput experiments. Developed nb_search Python package.',
    },
    {
        'year': '2017 — 2019',
        'title': 'Undergraduate Research',
        'org': 'West Virginia University',
        'description': 'Mathematical modeling and optimization with Dr. Fernando Lima. Won 2nd place at AIChE National Poster Competition.',
    },
    {
        'year': '2016 — 2019',
        'title': 'B.S. Chemical Engineering',
        'org': 'West Virginia University',
        'description': 'Graduated with Honors, Cum Laude.',
    },
]

OPENSOURCE = [
    {
        'name': 'TorchMIL',
        'description': 'A PyTorch library for deep multiple instance learning in computational pathology. Includes standardized benchmarks and reproducible implementations of attention-based MIL methods.',
        'url': 'https://github.com/Franblueee/torchmil',
        'role': 'Contributor',
    },
    {
        'name': 'HuggingFace Transformers',
        'description': 'Contributed to the HuggingFace Transformers library, the leading open-source platform for state-of-the-art NLP models.',
        'url': 'https://github.com/huggingface/transformers',
        'role': 'Contributor',
    },
]

SOCIAL_LINKS = [
    {'name': 'GitHub', 'url': 'https://github.com/loevlie', 'icon': 'github'},
    {'name': 'Google Scholar', 'url': 'https://scholar.google.com/citations?user=oGkEIYkAAAAJ&hl=en', 'icon': 'scholar'},

    {'name': 'LinkedIn', 'url': 'https://www.linkedin.com/in/dennisloevlie', 'icon': 'linkedin'},
    {'name': 'Bluesky', 'url': 'https://bsky.app/profile/dennisloevlie.bsky.social', 'icon': 'bluesky'},
    {'name': 'Medium', 'url': 'https://medium.com/@dennyloevlie', 'icon': 'medium'},
    {'name': 'Twitter', 'url': 'https://twitter.com/DennisLoevlie', 'icon': 'twitter'},
    {'name': 'Email', 'url': 'mailto:Loevliedenny@gmail.com', 'icon': 'email'},
]


# ---------------------------------------------------------------------------
# Lab notebook / demos archive
# ---------------------------------------------------------------------------
# Dated entries, each one a small public-thinking artifact. The Karpathy /
# Ciechanowski / Rush model — "things I'm currently exploring" rather than
# "polished portfolio." Newest first; render driver in templates/portfolio/demos.html.
#
# Schema:
#   slug          str  — anchor + element id
#   title         str
#   date          ISO date the demo was first published
#   updated       ISO date the demo last meaningfully changed (optional)
#   tags          list[str]
#   summary       short (1-line) blurb shown above the embed
#   what          markdown — what this demo is + how to use it
#   why           markdown — why I built it; what I was trying to learn
#   learned       markdown — what I now know that I didn't before
#   embed         template-snippet name in `portfolio/demos/embeds/{slug}.html`
#                 (kept inline rather than each becoming a separate URL).

NOW_PAGE = {
    # /now/ — Derek Sivers convention. Updated quarterly.
    # Last update: ALWAYS update this when editing the rest.
    'updated': '2026-04-19',
    'location': 'Boston, MA',
    'sections': [
        {
            'heading': 'Research',
            'body': (
                "Wrapping the camera-ready for our **CHIL 2026** benchmark "
                "(equal-contribution second author with Ethan Harvey, Hughes Lab) — "
                "showing a simple mean-pooling MIL baseline matches attention-MIL on "
                "4 of 6 moderate-sized neuroimage tasks while training **25× faster**. "
                "Spinning out a follow-up question: can we predict *before training* "
                "which datasets will need attention-based MIL vs simple pooling? "
                "Looking for cheap pre-training diagnostics."
            ),
        },
        {
            'heading': 'Reading',
            'body': (
                "**Tabular foundation models** (TabPFN, TabICL) — running my own "
                "experiments on small medical-tabular benchmarks where train sets are "
                "actually small. Also re-reading the **mechanistic interpretability** "
                "thread (Anthropic's [attribution-graphs](https://transformer-circuits.pub/2025/attribution-graphs/methods.html), "
                "Olah's circuits work) because the methods feel transferable to MIL "
                "instance-level attribution."
            ),
        },
        {
            'heading': 'Building',
            'body': (
                "This site (the design pass landing right now). Frozen Forecaster — "
                "the homepage TabICL vs XGBoost demo — is real inference cached from a "
                "Modal precompute. The Lab Notebook is the place where new things land "
                "first; longer pieces graduate to the blog as Explainers."
            ),
        },
        {
            'heading': 'Applying',
            'body': (
                "**ELLIS PhD program 2026 cohort** — primary advisor track at TRL Lab "
                "(Hulsebos + van de Meent). Open to FAANG research-internship "
                "conversations for summer 2026 / 2027. [Contact me](#contact)."
            ),
        },
        {
            'heading': 'Life',
            'body': (
                "Married to Brittany; planning the wedding. Cooking through *Salt Fat "
                "Acid Heat* one chapter at a time. Trail-running in the Middlesex Fells. "
                "Reading: *Brideshead Revisited*, currently."
            ),
        },
    ],
    'inspired_by': [
        ('Derek Sivers', 'https://sivers.org/now'),
        ('Cal Newport', 'https://calnewport.com/now/'),
        ('nownownow.com', 'https://nownownow.com/'),
    ],
}


DEMOS = [
    {
        'slug': 'nanoparticle-viewer',
        'title': 'AuPd Nanoparticle Viewer',
        'date': '2024-08-12',
        'updated': '',
        'tags': ['three.js', 'chemistry', 'visualization'],
        'summary': '55-atom Mackay icosahedron — the structure studied in '
                   'Loevlie et al., Acc. Chem. Res. (2023). Drag to rotate, '
                   'scroll to zoom, toggle Au-core ↔ Pd-core.',
        'what': "Real-time WebGL viewer of a 55-atom bimetallic Mackay icosahedron "
                "with a single-button core-swap and live cohesive-energy readout.",
        'why':  "Wanted a way to *see* the structure that the entire chemical-ordering "
                "argument in the paper hinges on, without forcing a reader to install "
                "ASE + NGLView. WebGL via three.js was the cheapest path to a "
                "frame-rate-locked rotation that doesn't fall over on a phone.",
        'learned': "Three.js's instanced meshes are fine for a few hundred atoms "
                   "but the per-atom material updates on core-swap are the real "
                   "cost — batch them or you drop frames on every toggle.",
        'embed': 'embed_nanoparticle.html',
    },
    {
        'slug': 'depth-estimation',
        'title': 'Client-Side Depth Estimation',
        'date': '2024-07-20',
        'updated': '',
        'tags': ['onnx', 'transformers.js', 'ml'],
        'summary': 'Drop an image, get a monocular depth map computed in your '
                   'browser via Depth Anything V2 (~27 MB ONNX, loads on first use).',
        'what': "Single-page upload that runs Depth Anything V2 entirely client-side "
                "via transformers.js + ONNX Runtime Web. Slide the divider to compare "
                "input ↔ predicted depth.",
        'why':  "Curious how far client-side ML had come for non-trivial vision "
                "models. Goal was zero server cost — the model is fetched from a "
                "Hugging Face Space and cached in IndexedDB after first run.",
        'learned': "WebGPU backend speeds inference 4–8× over WASM but adoption is "
                   "still spotty (Safari 26 in 2025 helped). The model fetch is "
                   "what users actually feel — service-worker prefetch is the "
                   "lever, not the inference itself.",
        'embed': 'embed_depth.html',
    },
]


NAV_LINKS = [
    # Trimmed 2026-04 to 4 primary items (Apple/Linear/Vercel pattern: ≤4 in
    # the top bar so the eye finds the page identity, not the menu). News +
    # Demos + Blog + Recipes all live under Explore as a single dropdown.
    {'label': 'About', 'href': '#about'},
    {'label': 'Research', 'href': '#publications', 'children': [
        {'label': 'Selected', 'href': '#publications'},
        {'label': 'Full List', 'href': '/publications/'},
        {'label': 'Experience', 'href': '#experience'},
        {'label': 'News', 'href': '#news'},
    ]},
    {'label': 'Writing', 'href': '/blog/', 'children': [
        {'label': 'Blog', 'href': '/blog/'},
        {'label': 'Featured Projects', 'href': '#projects'},
        {'label': 'All Projects', 'href': '/projects/'},
    ]},
    {'label': 'Demos', 'href': '/demos/', 'children': [
        {'label': 'Frozen Forecaster', 'href': '#demos'},
        {'label': 'Lab Notebook', 'href': '/demos/'},
        {'label': 'Recipes', 'href': '/recipes/'},
    ]},
    {'label': 'Contact', 'href': '#contact'},
]


# ── Recipes ──────────────────────────────────────────────────

RECIPES = [
    {
        'slug': 'finnish-salmon-soup',
        'emoji': '🍲',
        'title': 'Finnish Salmon Soup',
        'tagline': 'Comforting Salmon Soup in Under 30 Minutes',
        'description': "One of my all-time favorite soups \u2014 comforting, easy, and ready in under 30 minutes. It's similar to one my bestemor likes to make.",
        'credit_url': 'https://www.instagram.com/reels/DCjpO8UM405/',
        'credit_label': 'this post',
        'credit_verb': 'taken from',
        'time_minutes': 30,
        'servings': 2,
        'difficulty': 'Easy',
        'tags': ['Comfort Food', 'Finnish', 'Seafood', 'Quick & Easy'],
        'ingredients': [
            {'item': '400g salmon, cut into chunks', 'note': 'or your favorite fish!'},
            {'item': '250g potatoes, bite-sized', 'note': 'baby potatoes are my favorite'},
            {'item': '1 piece leek, sliced'},
            {'item': '1 carrot, cut into chunks'},
            {'item': '100ml cream'},
            {'item': '500ml fish broth', 'note': "I usually just use fish broth from Wegmans instead of water + a broth cube"},
            {'item': '1 bunch of dill, chopped'},
            {'item': '1 lemon, zested and juiced'},
            {'item': '1 tsp corn starch'},
        ],
        'steps': [
            'Heat a tablespoon of olive oil in a large pot. Saut\u00e9 the leeks with a pinch of salt for 2\u20133 minutes.',
            'Add the potatoes, carrots, and fish broth. Simmer for about 10 minutes, or until the veggies are almost tender.',
            'Gently stir in the salmon, lemon zest, dill, and cream. Bring to a boil, then reduce the heat and simmer for 5 minutes, until the fish is perfectly cooked.',
            'Mix corn starch with 1 tablespoon of hot water, then stir it into the soup to thicken slightly. Season with salt and pepper to taste.',
            'Ladle into bowls, squeeze in fresh lemon juice, and enjoy!',
        ],
    },
]
