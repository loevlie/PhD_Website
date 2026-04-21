"""Side projects / course projects / hackathon work shown under
/#projects and /projects/. `featured=True` surfaces above the fold."""

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
