# Scrapy settings for historycommons project
#

BOT_NAME = 'historycommons'
SPIDER_MODULES = ['historycommons.spiders']
NEWSPIDER_MODULE = 'historycommons.spiders'
USER_AGENT = 'historycommons_rescue (+https://github.com/robbiebyrd/historycommons)'
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 32
TELNETCONSOLE_ENABLED = True
