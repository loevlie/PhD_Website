"""Peer-reviewed publications + posters. `selected=True` promotes to
the homepage highlight block; the full list lives at /publications/."""

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
