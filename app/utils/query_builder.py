import re
from typing import List


def build_domain_query(domain: str) -> str:
    """
    Build a search query for a company domain.
    
    Args:
        domain: The company domain to search for
        
    Returns:
        Formatted search query string
    """
    # Remove protocol if present
    domain = re.sub(r'^https?://', '', domain)
    
    # Remove trailing slashes
    domain = domain.rstrip('/')
    
    # Format a query to find information about this domain
    return f'"{domain}" OR "www.{domain}" OR "https://{domain}" OR "http://{domain}"'


def build_full_query(full_name: str, domain: str) -> str:
    """
    Build a search query for a person's name at a company domain.
    
    This generates a complex query to find potential email variations.
    
    Args:
        full_name: The person's full name
        domain: The company domain
        
    Returns:
        Formatted search query string with name and potential email variations
    """
    # Remove protocol if present
    domain = re.sub(r'^https?://', '', domain)
    
    # Remove trailing slashes
    domain = domain.rstrip('/')
    
    # Split name into parts (assuming first name, last name format)
    name_parts = full_name.strip().split()
    
    # If we only have one name part, use it as is
    if len(name_parts) == 1:
        first_name = name_parts[0]
        last_name = ""
        first_initial = first_name[0].lower() if first_name else ""
        last_initial = ""
    else:
        # Extract first and last name if available (ignoring middle names)
        first_name = name_parts[0]
        last_name = name_parts[-1]
        
        # Get initials
        first_initial = first_name[0].lower() if first_name else ""
        last_initial = last_name[0].lower() if last_name else ""
    
    # Convert names to lowercase for email patterns
    first_name = first_name.lower()
    last_name = last_name.lower()
    
    # Generate potential email combinations
    email_variations = []
    
    # Only add variations if we have both first and last names
    if first_name and last_name:
        variations = [
            f"{first_name}@{domain}",
            f"{first_name}.{last_name}@{domain}",
            f"{first_name}{last_name}@{domain}",
            f"{first_initial}{last_name}@{domain}",
            f"{first_initial}.{last_name}@{domain}",
            f"{last_name}.{first_name}@{domain}",
            f"{last_name}{first_name}@{domain}",
            f"{first_name}_{last_name}@{domain}",
            f"{last_name}_{first_name}@{domain}",
            f"{first_name}-{last_name}@{domain}",
            f"{last_name}-{first_name}@{domain}",
            f"{last_name}@{domain}",
            f"{first_initial}{last_initial}@{domain}",
            f"{first_initial}.{last_initial}@{domain}",
        ]
        
        # Add Gmail variants
        variations.extend([
            f"{first_name}.{last_name}.{domain}@gmail.com",
            f"{first_name}{last_name}.{domain}@gmail.com",
        ])
        
        email_variations.extend(variations)
    elif first_name:
        # Only first name is available
        email_variations.extend([
            f"{first_name}@{domain}",
            f"{first_initial}@{domain}",
        ])
    elif last_name:
        # Only last name is available
        email_variations.extend([
            f"{last_name}@{domain}",
            f"{last_initial}@{domain}",
        ])
    
    # Add generic variations
    if first_name or last_name:
        generic_name = first_name or last_name
        email_variations.extend([
            f"office+{generic_name}@{domain}",
            f"contact+{generic_name}@{domain}",
            f"info+{generic_name}@{domain}",
        ])
    
    # Build the combined query
    email_query = " OR ".join([f'"{email}"' for email in email_variations])
    
    # Final query combining person name, domain, and email variations
    return f'"{full_name}" "@{domain}" ({email_query})'


def build_company_name_query(company_name: str) -> str:
    """
    Build a search query for a company name.
    
    Args:
        company_name: The company name to search for
        
    Returns:
        Formatted search query string
    """
    # Clean company name
    clean_name = company_name.strip()
    
    # Build query to find company information
    base_query = f'"{clean_name}"'
    
    # Add common extensions
    extensions = [
        "contact",
        "about",
        "team",
        "staff",
        "employees"
    ]
    
    extended_query = " OR ".join([f'"{clean_name} {ext}"' for ext in extensions])
    
    return f'{base_query} ({extended_query})'


def build_company_website_query(company_name: str) -> str:
    """
    Build a search query specifically to find a company's official website.
    
    Args:
        company_name: The company name to search for
        
    Returns:
        Formatted search query string
    """
    # Clean company name
    clean_name = company_name.strip()
    
    # Build query to find company's official website
    return f'"{clean_name}" official website'


def build_email_pattern_query(name_parts: List[str], domain: str) -> str:
    """
    Build a search query to find email patterns for a company.
    
    Args:
        name_parts: Parts of a sample person's name
        domain: The company domain
        
    Returns:
        Formatted search query string for email patterns
    """
    # This is a helper function that could be used to discover 
    # email patterns at a company using a sample person
    
    if len(name_parts) < 2:
        return f'"@{domain}" email'
    
    first_name = name_parts[0].lower()
    last_name = name_parts[-1].lower()
    
    query = f'"@{domain}" AND ("email pattern" OR "email format" OR '
    query += f'"{first_name}*{last_name}@{domain}" OR '
    query += f'"{last_name}*{first_name}@{domain}" OR '
    query += f'"{first_name[0]}*{last_name}@{domain}" OR '
    query += f'"{last_name[0]}*{first_name}@{domain}")'
    
    return query


# Add a main block to allow testing when run directly
if __name__ == "__main__":
    import sys
    
    # Test domain query
    test_domain = "impulsenotion.com"
    domain_query = build_domain_query(test_domain)
    print("\nDOMAIN QUERY TEST:")
    print(f"Domain: {test_domain}")
    print(f"Query: {domain_query}")
    
    # Test full search query
    test_name = "Sylia H."
    full_query = build_full_query(test_name, test_domain)
    print("\nFULL SEARCH QUERY TEST:")
    print(f"Name: {test_name}, Domain: {test_domain}")
    print(f"Query length: {len(full_query)} characters")
    print(f"Query: {full_query}")
    
    # Test company search query
    test_company = "Impulse Notion"
    company_query = build_company_name_query(test_company)
    print("\nCOMPANY QUERY TEST:")
    print(f"Company: {test_company}")
    print(f"Query: {company_query}")
    
    # When an argument is provided, use it as the full name for testing
    if len(sys.argv) > 1:
        custom_name = sys.argv[1]
        custom_domain = sys.argv[2] if len(sys.argv) > 2 else "example.com"
        custom_query = build_full_query(custom_name, custom_domain)
        print(f"\nCUSTOM QUERY TEST:")
        print(f"Name: {custom_name}, Domain: {custom_domain}")
        print(f"Query: {custom_query}") 