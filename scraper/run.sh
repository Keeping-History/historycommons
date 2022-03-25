if ! command -v python3 &> /dev/null
then
    echo "Python 3 could not be found"
    exit
fi
python3 -m venv .
source bin/activate
pip install -r requirements.txt
mkdir output
scrapy crawl historycommons -O output/historycommons.json
