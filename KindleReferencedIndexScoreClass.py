from datetime import date

class Review:
    def __init__(self):
        self.star       = 0
        self.context    = ''
        self.vote       = 0
        self.hashes     = None
class Referenced:
    def __init__(self):
        self.from_url = ''
        self.evaluation_date = None
class ScrapingData:
    def __init__(self):
        self.url = 'https://'
        self.normalized_url = 'https://'
        self.date = 0
        self.title = ''
        self.description = ''
        self.html = None
        self.html_context = ''
        self.amazon_rating = 0
        self.reviews = []
        self.craw_revision = 0
        self.evaluated = []
        self.count = 0
