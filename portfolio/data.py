"""
All portfolio content as Python data structures.
No database needed — academic portfolios change rarely.
"""

HERO = {
    'name': 'Dennis Johan Loevlie',
    'title': 'ELLIS PhD Student',
    'affiliation': 'CWI & University of Amsterdam',
    'bio': (
        'I am an ⭐ <a href="https://ellis.eu/research/phd-postdoc" target="_blank">ELLIS</a> PhD student at <a href="https://www.cwi.nl/" target="_blank">CWI</a> '
        'and the <a href="https://www.uva.nl/" target="_blank">University of Amsterdam</a>, '
        'working in the <a href="https://trl-lab.github.io/" target="_blank">Table Representation Learning Lab (TRLab)</a> '
        'and the <a href="https://amlab.science.uva.nl/" target="_blank">Amsterdam Machine Learning Lab (AMLab)</a>. '
        'I am advised by <a href="https://madelonhulsebos.github.io/" target="_blank">Madelon Hulsebos</a> '
        '(TRLab, CWI) and co-advised by <a href="https://jwvdm.github.io/" target="_blank">Jan-Willem van de Meent</a> '
        '(AMLab, UvA). '
        'My research focuses on <strong>multimodal tabular foundation models</strong>.'
    ),
    'bio_continued': (
        'Previously, I completed my M.S. in Computer Science at '
        '<a href="https://www.tufts.edu/" target="_blank">Tufts University</a>, '
        'where I was advised by '
        '<a href="https://www.michaelchughes.com/" target="_blank">Michael Hughes</a> '
        'on deep multiple instance learning for computational pathology. '
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
            {'label': 'Code', 'url': 'https://github.com/tufts-ml/TorchMIL'},
        ],
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
        'title': 'Gaussian Splatting PyTorch',
        'description': 'Implementation of 3D Gaussian Splatting for real-time radiance field rendering in PyTorch.',
        'tags': ['PyTorch', '3D Vision', 'Rendering'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Gaussian_Splatting_PyTorch'},
        ],
    },
    {
        'title': 'Depth Anything Video',
        'description': 'Monocular depth estimation for video sequences using the Depth Anything model.',
        'tags': ['Computer Vision', 'Depth Estimation', 'Video'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Depth-Anything-Video'},
            {'label': 'Demo', 'url': 'https://huggingface.co/spaces/JohanDL/Depth-Anything-Video'},
        ],
    },
    {
        'title': 'GPT4Readability',
        'description': 'CLI tool leveraging LLMs and vector databases with LangChain and llama.cpp to generate README files and suggest code improvements. Supports cloud and local open-source LLMs across 15 languages.',
        'tags': ['NLP', 'LangChain', 'Open Source'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/GPT4Readability'},
            {'label': 'Demo', 'url': 'https://huggingface.co/spaces/JohanDL/GPT4Readability'},
        ],
    },
    {
        'title': 'SkinsAI',
        'description': 'Free diagnosis tool classifying moles as benign or malignant using a PyTorch CNN. Won 2nd place out of 24 teams at The Pitt Challenge Hackathon.',
        'tags': ['Medical AI', 'PyTorch', 'Hackathon'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/SkinsAI'},
            {'label': 'Competition', 'url': 'https://pittchallenge.com'},
            {'label': 'Devpost', 'url': 'https://devpost.com/software/skinsai'},
        ],
    },
    {
        'title': 'Aqueous Solubility Prediction',
        'description': 'Machine learning models for predicting aqueous solubility of chemical compounds.',
        'tags': ['Cheminformatics', 'ML', 'Chemistry'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Aqueous_Solubility'},
            {'label': 'Kaggle', 'url': 'https://www.kaggle.com/competitions/euos-slas/overview'},
        ],
    },
    {
        'title': 'ASL Active Learning',
        'description': 'Active learning framework for American Sign Language recognition with efficient labeling.',
        'tags': ['Active Learning', 'Computer Vision', 'ASL'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/ASL_Active_Learning'},
        ],
    },
    {
        'title': 'Disparity Maps',
        'description': 'Stereo vision disparity map generation for depth perception from image pairs.',
        'tags': ['Computer Vision', 'Stereo', 'Depth'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/DL_Project_PSMNet'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
            {'label': 'PDF', 'url': 'https://www.loevliedl.com/static/Portfolio/PDF/DL_Final.pdf'},
        ],
    },
    {
        'title': 'QA Model',
        'description': 'Question answering system built with transformer-based architectures.',
        'tags': ['NLP', 'Transformers', 'QA'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Question_Answer_Model'},
            {'label': 'Course', 'url': 'http://demo.clab.cs.cmu.edu/NLP/'},
        ],
    },
    {
        'title': 'Face Verification',
        'description': 'Face verification system using deep metric learning and siamese networks.',
        'tags': ['Computer Vision', 'Biometrics', 'Deep Learning'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Face_Verification'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
        ],
    },
    {
        'title': 'Rhine Water Level Prediction',
        'description': 'Time series forecasting for Rhine river water levels using ML models.',
        'tags': ['Time Series', 'Forecasting', 'Environmental'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Rhine_Water_Level_Prediction'},
        ],
    },
    {
        'title': 'Speech Recognition',
        'description': 'Automatic speech recognition system using deep learning architectures.',
        'tags': ['Speech', 'Deep Learning', 'Audio'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Speech_Recognition'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
        ],
    },
    {
        'title': 'Speech to Text',
        'description': 'End-to-end speech-to-text transcription pipeline with attention mechanisms.',
        'tags': ['Speech', 'NLP', 'Seq2Seq'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Speech_to_Text_Transcription'},
            {'label': 'Course', 'url': 'https://deeplearning.cs.cmu.edu/F21/index.html'},
        ],
    },
    {
        'title': 'ML Codes',
        'description': 'Collection of machine learning algorithm implementations from scratch.',
        'tags': ['ML', 'Algorithms', 'Education'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/ML_Codes'},
            {'label': 'Course', 'url': 'http://www.cs.cmu.edu/~mgormley/courses/10601/'},
        ],
    },
    {
        'title': 'Patient Stay Prediction',
        'description': 'Predicting patient length of stay in hospitals using clinical data and ML.',
        'tags': ['Healthcare', 'ML', 'Prediction'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/Pitt-Hackathon'},
            {'label': 'Slides', 'url': 'https://docs.google.com/presentation/d/1I-Sl-MyEbZGwBV4Ytol2Y7GEi3kSyOyh1Y8aRKm0H8s/edit?usp=sharing'},
        ],
    },
    {
        'title': 'nb_search',
        'description': 'Search tool for finding content across Jupyter notebooks in a repository.',
        'tags': ['Developer Tools', 'Jupyter', 'Search'],
        'links': [
            {'label': 'Code', 'url': 'https://github.com/loevlie/nb_search'},
            {'label': 'PyPI', 'url': 'https://pypi.org/project/nb-search/'},
        ],
    },
]

TIMELINE = [
    {
        'year': '2026 —',
        'title': 'ELLIS PhD Student',
        'org': 'CWI & University of Amsterdam',
        'description': 'Researching multimodal tabular foundation models. Advised by Madelon Hulsebos (TRLab, CWI) and co-advised by Jan-Willem van de Meent (AMLab, UvA).',
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
        'description': 'GPA: 3.95. Research on deep MIL for computational pathology with Dr. Michael Hughes. Also working with Dr. Jivko Sinapov on vision-language models and reinforcement learning.',
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
        'url': 'https://github.com/tufts-ml/TorchMIL',
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

NAV_LINKS = [
    {'label': 'About', 'href': '#about'},
    {'label': 'News', 'href': '#news'},
    {'label': 'Publications', 'href': '#publications'},
    {'label': 'Projects', 'href': '#projects'},
    {'label': 'Demos', 'href': '#demos'},
    {'label': 'Experience', 'href': '#experience'},
    {'label': 'Open Source', 'href': '#opensource'},
    {'label': 'Contact', 'href': '#contact'},
]
