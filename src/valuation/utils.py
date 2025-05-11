from datetime import datetime

def safe_float(value, default=0.0):
    """Safely convert a value to float, returning a default if conversion fails."""
    try:
        if isinstance(value, str):
            value = value.replace(',', '') # Handle commas in numbers from sheets
        return float(value) if value not in [None, 'None', ''] else default
    except (ValueError, TypeError):
        return default

def retrieve_date(): # Renamed from retrieve_date_str for consistency with original script
    """Returns the current date formatted as 'Mon-DD'."""
    return datetime.today().strftime('%b-%d')

def prompt_user_choice(options_list, prompt_message="Please choose an option:"):
    """Prompts user to select from a list of options with search functionality."""
    if not options_list:
        print(f"No options provided for: {prompt_message}")
        manual_input = input(f"{prompt_message} (No predefined options, please enter manually): ").strip()
        return manual_input

    print(f"\n{prompt_message}")
    print("You can type part of the name to search for matches, or its number from the list.")
    
    while True:
        search_input = input(f"Search or type number: ").strip()
        
        if search_input.isdigit():
            try:
                choice_idx = int(search_input) -1
                if 0 <= choice_idx < len(options_list):
                    return options_list[choice_idx]
                else:
                    print("Invalid number. Please choose from the list below or type to search.")
            except ValueError: 
                pass 

        search_term_lower = search_input.lower()
        matching_options = [opt for opt in options_list if search_term_lower in str(opt).lower()]

        if not matching_options:
            print("No matches found. Displaying all options (max 20):")
            for idx, opt in enumerate(options_list[:20], start=1):
                print(f"{idx}. {opt}")
            if len(options_list) > 20: print("...and more. Please refine your search.")
            continue

        print("\nMatches found:")
        for idx, opt in enumerate(matching_options[:15], start=1): # Show top 15 matches
            print(f"{idx}. {opt}")
        
        if len(matching_options) > 15:
            print(f"...and {len(matching_options) - 15} more matches. Refine your search or choose by number from this filtered list.\n")
        else:
            print("")

        selected_option_input = input("Type your exact choice from the matches above (or number from this filtered list): ").strip()
        
        if selected_option_input.isdigit():
            try: 
                choice_idx = int(selected_option_input) -1
                if 0 <= choice_idx < len(matching_options): 
                    return matching_options[choice_idx]
            except ValueError:
                pass 
        
        selected_exact = [opt for opt in matching_options if str(opt).lower() == selected_option_input.lower()]
        if selected_exact:
            return selected_exact[0]
        else:
            print("Invalid selection. Please type the exact name or number from the list.\n") 