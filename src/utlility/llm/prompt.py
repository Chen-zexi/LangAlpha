import pandas as pd
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate

class prompts:
    news_sentiment_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a financial analyst. You are given a list of news articles and a ticker. You need to analyze the news and provide a summary of the news and the sentiment of the news.
                    You should also identify if the news mentioned any upcoming key events that could impact the stock price.
                """,
            ),
            (
                "human",
                """Based on the following news, create the investment signal:
                    News Data for {ticker}
                    {llm_news}
                """,
            ),
        ]
    )

        
    news_sentiment_by_date_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                    """You are a financial analyst. You are given a list of news articles and a ticker on a specific date. You need to analyze the news and provide a summary of the news and the sentiment of the news.
                    You should explain why the stock price might move up or down based on the news.
                    """,
                ),
                (
                    "human",
                    """Based on the following news, create the investment signal:

                    News Data for {ticker} on {date}:
                    {llm_news}
                    You response should be in the following format:
                    Summary: a short summary of the news
                    Sentiment: categorized by strongly positive, positive, neutral, negative, strongly negative
                    Reasoning: a short reasoning for the sentiment
                    Date: {date}
                    Stock Price Movement: does the news suggest the moevment of stock price on that day?
                    """
                    ,
                ),
            ]
        )
        
        