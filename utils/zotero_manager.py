# utils/zotero_manager.py

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pyzotero import zotero
from slugify import slugify

load_dotenv()


class ZoteroItem(BaseModel):
    """
    Represents metadata about a Zotero item.
    """

    key: str = Field(..., description="Unique key of the item")
    title: str = Field(..., description="Title of the item")
    abstract: Optional[str] = Field(None, description="Abstract or note of the item")
    full_text: Optional[str] = Field(None, description="Full text of the item")
    authors: Optional[List[str]] = Field(
        None, description="List of authors"
    )  # Make optional
    doi: Optional[str] = Field(None, description="Digital Object Identifier (DOI)")
    year: Optional[int] = Field(None, description="Publication year")
    item_type: Optional[str] = Field(
        None, description="Type of the item (e.g., journalArticle)"
    )  # Make optional
    url: Optional[str] = Field(None, description="URL of the item")


class ZoteroCollection(BaseModel):
    """
    Represents a Zotero collection with metadata.
    """

    key: str = Field(..., description="Unique identifier for the collection.")
    name: str = Field(..., description="Name of the collection.")
    number_of_items: int = Field(
        ..., description="Number of items contained in the collection."
    )


class ZoteroManager:
    '''
    #### Example Usage ####

    zotero_library_id = os.getenv("ZOTERO_LIBRARY_ID")
    zotero_library_type = "user"  # or "group"
    zotero_api_access_key = os.getenv("ZOTERO_API_ACCESS_KEY")

    zotero_manager = ZoteroManager(zotero_library_id, zotero_library_type, zotero_api_access_key)

    #### GET Zotero topics (Collections) ####
    zotero_collections = zotero_manager.get_collections()
    # print(zotero_collections)

    #### Zotero collections parsed with pydantic ####
    zotero_collection_lists = zotero_manager.list_zotero_collections(zotero_collections)
    # print(zotero_collection_lists)
    """
    [
        ZoteroCollection(key='IXU5ZWRM', name='RR 10', number_of_items=0),
        ZoteroCollection(key='G6AZZGPQ', name='RR 9', number_of_items=0),
        ZoteroCollection(key='DZ45SJHF', name='RR 8', number_of_items=0),
        ZoteroCollection(key='DM5FVG74', name='RR 7', number_of_items=0),
        ZoteroCollection(key='43N5CI48', name='RR 6', number_of_items=0),
        ZoteroCollection(key='2TCX6JC2', name='RR 5', number_of_items=0),
        ZoteroCollection(key='QVSNAJWV', name='RR 4', number_of_items=0),
        ZoteroCollection(key='96UJANPP', name='Ebola Virus', number_of_items=17),
        ZoteroCollection(key='UB7AEMB6', name='GeneXpert', number_of_items=31),
        ZoteroCollection(key='UDQ9JSD9', name='Vaccine coverage', number_of_items=22),
        ZoteroCollection(key='SGNLNIAT', name='Zotero Collection Pastan', number_of_items=227)
    ]
    """

    #### Collections with items ####
    filtered_zotero_collection_lists = zotero_manager.filter_and_return_collections_with_items(zotero_collection_lists)
    # print(filtered_zotero_collection_lists)
    """
    [
        {'key': '96UJANPP', 'name': 'Ebola Virus', 'number_of_items': 17},
        {'key': 'UB7AEMB6', 'name': 'GeneXpert', 'number_of_items': 31},
        {'key': 'UDQ9JSD9', 'name': 'Vaccine coverage', 'number_of_items': 22},
        {'key': 'SGNLNIAT',
        'name': 'Zotero Collection Pastan',
        'number_of_items': 227}
    ]
    """

    #### Collection by name from a list of zotero collections
    ebola_virus_collection = zotero_manager.find_zotero_collection_by_name(zotero_collection_lists, "Ebola Virus")
    # print(ebola_virus_collection)
    """ZoteroCollection(key='96UJANPP', name='Ebola Virus', number_of_items=17)"""
    # print(ebola_virus_collection.model_dump())
    """{'key': '96UJANPP', 'name': 'Ebola Virus', 'number_of_items': 17}"""

    #### Get single collection by key ####
    ebola_virus_collection_key = "96UJANPP" # Ebola Virus
    ebola_virus_collection = zotero_manager.get_collection_by_key(ebola_virus_collection_key)
    # print(ebola_virus_collection)
    """
    {
        'key': '96UJANPP',
        'version': 72,
        'library': {'type': 'user',
        'id': 11201324,
        'name': 'pjlus',
        'links': {'alternate': {'href': 'https://www.zotero.org/pjlus',
            'type': 'text/html'}}},
        'links': {'self': {'href': 'https://api.zotero.org/users/11201324/collections/96UJANPP',
        'type': 'application/json'},
        'alternate': {'href': 'https://www.zotero.org/pjlus/collections/96UJANPP',
        'type': 'text/html'}},
        'meta': {'numCollections': 0, 'numItems': 17},
        'data': {'key': '96UJANPP',
        'version': 72,
        'name': 'Ebola Virus',
        'parentCollection': False,
        'relations': {}}
    }
    """

    #### Get collection items by collection key ####
    ebora_virus_collection_items = zotero_manager.get_collection_items(ebola_virus_collection_key)
    print(len(ebora_virus_collection_items))
    # print(ebora_virus_collection_items[:2])

    #### Getting zotero collection items and full text
    # Here the collections have been parsed using the zotero item pydantic model defined in the zotero manager.
    ####
    ebora_virus_zotero_collection_items = zotero_manager.get_collection_zotero_items_by_key(ebola_virus_collection_key)
    # print(len(ebora_virus_zotero_collection_items))
    # print(ebora_virus_zotero_collection_items[0])

    #### Get item children (attachments)
    # Listed items in zotero are items together with their attachments (pdf content)
    ####
    zotero_manager.get_item_children("2Q7HFERL")

    #### Get an item full text ####
    zotero_manager.get_item_full_text("BMYMEW76")["content"]

    #### Save the item pdf content to disc ####
    ## Function to save a pdf file
    zotero_manager.save_item_file("BMYMEW76")

    #### Export zotero collection items to json ####
    ebora_virus_zotero_items_json = zotero_manager.zotero_items_to_json(ebora_virus_zotero_collection_items)
    print(len(ebora_virus_zotero_items_json))
    # print(ebora_virus_zotero_items_json[0])
    ## Save to disc
    zotero_manager.write_zotero_items_to_json_file(ebora_virus_zotero_items_json, "zotero_data/ebora_virus_zotero_items.json")
    '''

    def __init__(self, library_id: str, library_type: str, api_key: str):
        self.zot = zotero.Zotero(library_id, library_type, api_key)

    def create_zotero_item_from_json(self, json_obj: Dict[str, Any]) -> ZoteroItem:
        """
        Creates a ZoteroItem instance from a JSON object.

        Args:
            json_obj (Dict[str, Any]): A JSON object containing the Zotero item data.
                The JSON structure is expected to have a 'data' field which includes
                the metadata for the Zotero item.

        Returns:
            ZoteroItem: An instance of ZoteroItem populated with the data extracted
                from the JSON object. The fields include key, title, abstract, authors,
                doi, year, item_type, and url.
        """
        data = json_obj.get("data", {})

        # Extract item full text from it's attachement
        key = data.get("key")
        full_text = self.get_full_text_from_children(key)

        # Extract the list of authors
        authors = [
            f"{creator.get('name', '')} {creator.get('firstName', '')} {creator.get('lastName', '')}".strip()
            for creator in data.get("creators", [])
            if creator.get("creatorType") == "author"
        ]

        # Create the ZoteroItem instance
        zotero_item = ZoteroItem(
            key=data.get("key"),
            title=data.get("title"),
            abstract=data.get("abstractNote"),
            full_text=full_text,
            authors=authors,
            doi=data.get("DOI"),
            # year=int(data.get('date', '').split('-')[0]) if data.get('date') else None,
            item_type=data.get("itemType"),
            url=data.get("url"),
        )

        return zotero_item

    def create_zotero_collection(
        self, collection_dict: Dict[str, Any]
    ) -> ZoteroCollection:
        """
        Converts a dictionary representing a Zotero collection into a ZoteroCollection instance.

        Args:
            collection_dict (Dict[str, Any]): A dictionary containing data for a Zotero collection.
                The expected structure includes keys 'data' and 'meta' from which relevant fields
                such as 'key', 'name', and 'numItems' are extracted.

        Returns:
            ZoteroCollection: An instance of ZoteroCollection populated with the data extracted
                from the input dictionary.
        """
        data = collection_dict.get("data", {})
        meta = collection_dict.get("meta", {})

        zotero_collection = ZoteroCollection(
            key=data.get("key"),
            name=data.get("name"),
            number_of_items=meta.get("numItems", 0),
        )

        return zotero_collection

    def list_zotero_collections(
        self, collection_items: List[Dict[str, Any]]
    ) -> List[ZoteroCollection]:
        """
        Converts a list of dictionaries representing Zotero collections into a list of ZoteroCollection instances.

        Args:
            collection_items (List[Dict[str, Any]]): A list of collection items, each containing data for a Zotero collection.
                Each dictionary is expected to have a 'data' key with nested 'key' and 'name' fields, and a 'meta' key
                with a 'numItems' field.

        Returns:
            List[ZoteroCollection]: A list of ZoteroCollection instances populated with the data extracted
                from the input dictionaries.
        """
        collections = [
            self.create_zotero_collection(collection_item)
            for collection_item in collection_items
        ]
        return collections

    def list_all_papers(self) -> List[ZoteroItem]:
        """
        Lists all papers (journal articles) in your Zotero library.

        Returns:
            List of ZoteroItem objects representing the papers in your library.
        """
        # print(self.zot.items())
        results = self.zot.items(itemType="journalArticle")
        # print(f"results: {results}")

        papers = []

        for item in results:
            zotero_item = self.create_zotero_item_from_json(item)
            papers.append(zotero_item)

        return papers

    def list_items(self, limit: int = 5):
        return self.zot.items(limit=limit)

    def query_items(self, query: str, limit: int = 10) -> List[ZoteroItem]:
        """
        Queries Zotero for items matching the given query.

        Args:
            query: The search query.
            limit: Maximum number of items to return.

        Returns:
            List of ZoteroItem objects representing the search results.
        """
        results = self.zot.items(q=query, limit=limit)

        return [
            self.create_zotero_item_from_json(item) for item in results
        ]  # Use ** to unpack the dictionary

    def get_item_by_key(self, key: str) -> ZoteroItem:
        """
        Retrieves a Zotero item by its key.

        Args:
            key: The unique key of the item.

        Returns:
            ZoteroItem object representing the retrieved item.
        """
        item = self.zot.item(key)
        return self.create_zotero_item_from_json(item)

    def get_item_by_doi(self, doi: str) -> Optional[ZoteroItem]:
        """
        Searches for a Zotero item by its DOI.

        Args:
            doi: The DOI of the item.

        Returns:
            ZoteroItem object if found, otherwise None.
        """
        results = self.zot.items(q=doi)
        for item in results:
            if item["data"].get("DOI") == doi:
                self.create_zotero_item_from_json(item)
        return None

    def get_item_tags(self, item_key: str) -> List[str]:
        """
        Retrieves the tags associated with a Zotero item.

        Args:
            item_key: The unique key of the item.

        Returns:
            List of strings representing the tags associated with the item.
        """
        return self.zot.item_tags(item_key)

    def get_collections(self) -> List[Dict[str, Any]]:
        """
        Retrieves the list of collections in your Zotero library.

        Returns:
            List of dictionaries representing the collections.
        """
        return self.zot.collections()

    def get_collection_by_key(self, collection_key: str) -> Dict[str, Any]:
        """
        Retrieves a collection by its key.

        Args:
            collection_key: The unique key of the collection.

        Returns:
            Dictionary representing the collection.
        """
        return self.zot.collection(collection_key)

    def get_collection_items(self, collection_key: str) -> List[Dict[str, Any]]:
        """
        Retrieves the items in a collection.

        Args:
            collection_key: The unique key of the collection.

        Returns:
            List of dictionaries representing the items in the collection.
        """
        return self.zot.collection_items(collection_key, itemType="journalArticle")

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        """
        Retrieves the children of a Zotero item.

        Args:
            item_key: The unique key of the item.

        Returns:
            List of dictionaries representing the children of the item.
        """
        return self.zot.children(item_key)

    def get_collection_zotero_items_by_key(
        self, collection_key: str
    ) -> List[ZoteroItem]:
        """
        Retrieves the items in a collection.

        Args:
            collection_key: The unique key of the collection.

        Returns:
            List of ZoteroItem objects representing the items in the collection.
        """
        items = self.zot.collection_items(collection_key, itemType="journalArticle")
        return [self.create_zotero_item_from_json(item) for item in items]

    def filter_and_return_collections_with_items(
        self, zotero_collections: List[ZoteroCollection]
    ) -> List[Dict[str, Any]]:
        """
        Filters a list of ZoteroCollection instances to return only those with more than one item,
        and returns them as a list of dictionaries.

        Args:
          zotero_collections (List[CollectionModel]): A list of CollectionModel instances.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing collections with more than one item.
        """
        filtered_collections = [
            collection.model_dump()
            for collection in zotero_collections
            if collection.number_of_items > 0
        ]
        return filtered_collections

    def find_zotero_collection_by_name(
        self, zotero_collections: List[ZoteroCollection], name: str
    ) -> ZoteroCollection:
        """
        Finds and returns a ZoteroCollection instance by its name.

        Args:
            zotero_collections (List[CollectionModel]): A list of CollectionModel instances.
            name (str): The name of the collection to find.

        Returns:
            ZoteroCollection: The ZoteroCollection instance that matches the given name.

        Raises:
            ValueError: If no collection with the given name is found.
        """
        for collection in zotero_collections:
            if collection.name == name:
                return collection
        raise ValueError(f"Collection with name '{name}' not found.")

    def zotero_items_to_json(
        self, zotero_items: List[ZoteroItem]
    ) -> List[Dict[str, Any]]:
        """
        Converts a list of ZoteroItem instances into a JSON-compatible list of dictionaries.

        Args:
            zotero_items (List[ZoteroItem]): A list of ZoteroItem instances.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the Zotero items.
                Each dictionary is a JSON-compatible representation of a ZoteroItem.
        """
        items = [item for item in zotero_items if item.abstract or item.full_text]

        return [item.model_dump() for item in items]

    def write_zotero_items_to_json_file(
        self, zotero_items_json: List[Dict[str, Any]], file_path: str
    ) -> None:
        """
        Writes a JSON object of Zotero items to a JSON file.

        Args:
            zotero_items_json (List[Dict[str, Any]]): A JSON-compatible list of dictionaries
                representing Zotero items.
            file_path (str): The file path where the JSON file should be written.

        Returns:
            None
        """
        with open(file_path, "w") as json_file:
            json.dump(zotero_items_json, json_file, indent=2)

    def get_item_full_text(self, key: str) -> Optional[dict]:
        """
        Retrieves an item by its key and dumps it file.

        Args:
              key: The unique key of the item.

        Returns:
              A dictionary containing the metadata for full text:
        """

        try:
            return self.zot.fulltext_item(key)
        except Exception as e:
            print(f"Error: {str(e)}")
            return None

    def get_full_text_from_children(self, key: str) -> Optional[str]:
        """
        Retrieves an item by its key and dumps it file.

        Args:
              key: The unique key of the item.

        Returns:
              A text containing the metadata for full text:
        """
        children_items = self.get_item_children(key)
        full_text = ""
        if children_items:
            for item in children_items:
                if item.get("data", {}).get("itemType") == "attachment":
                    content_dict = self.get_item_full_text(
                        item.get("data", {}).get("key", "")
                    )
                    if content_dict is not None:
                        content = content_dict.get("content", "")
                        full_text += content + "\n"

        return full_text

    def save_item_file(self, key: str) -> None:
        """
        Retrieves an item by its key and dumps it file.

        Args:
              key: The unique key of the item.
        """
        item = self.zot.item(key)
        zotero_item = self.create_zotero_item_from_json(item)
        item_title = slugify(zotero_item.title)
        try:
            self.zot.dump(key, f"{item_title}.pdf", "zotero_data")
        except Exception as e:
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    """Sample driver code"""
    zotero_library_id = os.getenv("ZOTERO_LIBRARY_ID")
    zotero_library_type = "user"  # or "group"
    zotero_api_access_key = os.getenv("ZOTERO_API_ACCESS_KEY")

    zotero_manager = ZoteroManager(
        zotero_library_id, zotero_library_type, zotero_api_access_key
    )

    #### GET Zotero topics (Collections) ####
    zotero_collections = zotero_manager.get_collections()
    # print(zotero_collections)

    #### Zotero collections parsed with pydantic ####
    zotero_collection_lists = zotero_manager.list_zotero_collections(zotero_collections)
    # print(zotero_collection_lists)
    """
    [
        ZoteroCollection(key='IXU5ZWRM', name='RR 10', number_of_items=0),
        ZoteroCollection(key='G6AZZGPQ', name='RR 9', number_of_items=0),
        ZoteroCollection(key='DZ45SJHF', name='RR 8', number_of_items=0),
        ZoteroCollection(key='DM5FVG74', name='RR 7', number_of_items=0),
        ZoteroCollection(key='43N5CI48', name='RR 6', number_of_items=0),
        ZoteroCollection(key='2TCX6JC2', name='RR 5', number_of_items=0),
        ZoteroCollection(key='QVSNAJWV', name='RR 4', number_of_items=0),
        ZoteroCollection(key='96UJANPP', name='Ebola Virus', number_of_items=17),
        ZoteroCollection(key='UB7AEMB6', name='GeneXpert', number_of_items=31),
        ZoteroCollection(key='UDQ9JSD9', name='Vaccine coverage', number_of_items=22),
        ZoteroCollection(key='SGNLNIAT', name='Zotero Collection Pastan', number_of_items=227)
    ]
    """

    #### Collections with items ####
    filtered_zotero_collection_lists = (
        zotero_manager.filter_and_return_collections_with_items(zotero_collection_lists)
    )
    # print(filtered_zotero_collection_lists)
    """
    [
        {'key': '96UJANPP', 'name': 'Ebola Virus', 'number_of_items': 17},
        {'key': 'UB7AEMB6', 'name': 'GeneXpert', 'number_of_items': 31},
        {'key': 'UDQ9JSD9', 'name': 'Vaccine coverage', 'number_of_items': 22},
        {'key': 'SGNLNIAT',
        'name': 'Zotero Collection Pastan',
        'number_of_items': 227}
    ]
    """

    #### Collection by name from a list of zotero collections
    ebola_virus_collection = zotero_manager.find_zotero_collection_by_name(
        zotero_collection_lists, "Ebola Virus"
    )
    # print(ebola_virus_collection)
    """ZoteroCollection(key='96UJANPP', name='Ebola Virus', number_of_items=17)"""
    # print(ebola_virus_collection.model_dump())
    """{'key': '96UJANPP', 'name': 'Ebola Virus', 'number_of_items': 17}"""

    #### Get single collection by key ####
    ebola_virus_collection_key = "96UJANPP"  # Ebola Virus
    ebola_virus_collection = zotero_manager.get_collection_by_key(
        ebola_virus_collection_key
    )
    # print(ebola_virus_collection)
    """
    {
        'key': '96UJANPP',
        'version': 72,
        'library': {'type': 'user',
        'id': 11201324,
        'name': 'pjlus',
        'links': {'alternate': {'href': 'https://www.zotero.org/pjlus',
            'type': 'text/html'}}},
        'links': {'self': {'href': 'https://api.zotero.org/users/11201324/collections/96UJANPP',
        'type': 'application/json'},
        'alternate': {'href': 'https://www.zotero.org/pjlus/collections/96UJANPP',
        'type': 'text/html'}},
        'meta': {'numCollections': 0, 'numItems': 17},
        'data': {'key': '96UJANPP',
        'version': 72,
        'name': 'Ebola Virus',
        'parentCollection': False,
        'relations': {}}
    }
    """

    #### Get collection items by collection key ####
    ebora_virus_collection_items = zotero_manager.get_collection_items(
        ebola_virus_collection_key
    )
    print(len(ebora_virus_collection_items))
    # print(ebora_virus_collection_items[:2])

    #### Getting zotero collection items and full text
    # Here the collections have been parsed using the zotero item pydantic model defined in the zotero manager.
    ####
    ebora_virus_zotero_collection_items = (
        zotero_manager.get_collection_zotero_items_by_key(ebola_virus_collection_key)
    )
    # print(len(ebora_virus_zotero_collection_items))
    # print(ebora_virus_zotero_collection_items[0])

    #### Get item children (attachments)
    # Listed items in zotero are items together with their attachments (pdf content)
    ####
    zotero_manager.get_item_children("2Q7HFERL")

    #### Get an item full text ####
    zotero_manager.get_item_full_text("BMYMEW76")["content"]

    #### Save the item pdf content to disc ####
    ## Function to save a pdf file
    zotero_manager.save_item_file("BMYMEW76")

    #### Export zotero collection items to json ####
    ebora_virus_zotero_items_json = zotero_manager.zotero_items_to_json(
        ebora_virus_zotero_collection_items
    )
    print(len(ebora_virus_zotero_items_json))
    # print(ebora_virus_zotero_items_json[0])
    ## Save to disc
    zotero_manager.write_zotero_items_to_json_file(
        ebora_virus_zotero_items_json, "zotero_data/ebora_virus_zotero_items.json"
    )
