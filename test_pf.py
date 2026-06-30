import asyncio
from listing_link_parser import extract_permit_from_listing_url

url = input("PF/Bayut link: ").strip()

permit = asyncio.run(extract_permit_from_listing_url(url))

print("PERMIT:", permit)
