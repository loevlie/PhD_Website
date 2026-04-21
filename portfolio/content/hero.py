"""Hero block on the homepage + the `currently:` line on /notebook/."""

HERO = {
    'name': 'Dennis Johan Loevlie',
    'title': 'ELLIS PhD Student',
    'affiliation': 'Centrum Wiskunde & Informatica & University of Amsterdam',
    'bio': (
        'I am an <a href="https://ellis.eu/research/phd-postdoc" target="_blank">ELLIS</a> PhD student at the <a href="https://www.cwi.nl/" target="_blank">Centrum Wiskunde & Informatica (CWI)</a> '
        'and the <a href="https://www.uva.nl/" target="_blank">University of Amsterdam</a> (UvA), '
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

CURRENTLY = (
    # Single-line "what I'm thinking about right now" string for the
    # /notebook/ sticky bar. Edit by hand. HTML allowed (use <em> sparingly).
    "Pre-training a small SAE on Pythia-410M. Re-reading the <em>μP</em> paper. "
    "Writing an explainer on multiple-instance learning for non-medical-imaging readers."
)
