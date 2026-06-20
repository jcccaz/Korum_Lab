from neo4j import GraphDatabase
from korum_lab.config import NEO4J_URI, NEO4J_AUTH, NEO4J_DATABASE

class GraphConnection:
    """Singleton-style Graph Connection Manager"""
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        return cls._driver
    
    @classmethod
    def get_session(cls):
        return cls.get_driver().session(database=NEO4J_DATABASE)

    @classmethod
    def close(cls):
        if cls._driver is not None:
            cls._driver.close()
            cls._driver = None
