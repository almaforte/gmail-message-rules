from setuptools import setup, find_packages

setup(
    name="gmail-message-rules",
    version="1.0.0",
    description=(
        "Regole obbligatorie di formattazione per le email inviate dai "
        "progetti di Alberto: niente trattini lunghi, niente firma "
        "scritta a mano duplicata, html_body sempre obbligatorio, "
        "spaziatura corretta tra blocchi HTML."
    ),
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "beautifulsoup4>=4.11",
    ],
    python_requires=">=3.9",
)
