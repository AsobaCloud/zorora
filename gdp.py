Certainly! Below is a Python script that generates an HTML page containing an image named `gdp.png` and some relevant information about the graph. This script uses Python's built-in `webbrowser` module to open the generated HTML file in a web browser.

```python
import os
import webbrowser

def generate_html_page(image_path, title, description):
    """
    Generates an HTML page with an image and a description.

    :param image_path: Path to the image file (e.g., 'gdp.png').
    :param title: Title of the image/graph.
    :param description: Description of the image/graph.
    """
    # Ensure the image file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"The image file {image_path} does not exist.")

    # HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: auto;
            }}
            img {{
                width: 100%;
                height: auto;
                display: block;
                margin-bottom: 20px;
            }}
            h1 {{
                text-align: center;
            }}
            p {{
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            <img src="{image_path}" alt="{title}">
            <p>{description}</p>
        </div>
    </body>
    </html>
    """

    # Write the HTML content to a file
    html_file_path = 'gdp_report.html'
    with open(html_file_path, 'w', encoding='utf-8') as file:
        file.write(html_content)

    # Open the HTML file in a web browser
    webbrowser.open(f'file://{os.path.abspath(html_file_path)}')

def main():
    # Define the image path, title, and description
    image_path = 'gdp.png'
    title = 'GDP Growth Over Time'
    description = (
        "This graph illustrates the GDP growth of a country over a period of several years. "
        "The x-axis represents the years, and the y-axis represents the GDP in billions of dollars. "
        "The data shows a steady increase in GDP with some fluctuations due to economic factors."
    )

    # Generate the HTML page
    generate_html_page(image_path, title, description)

if __name__ == "__main__":
    main()
```

### Explanation:

1. **Function `generate_html_page`**:
   - Takes three parameters: `image_path`, `title`, and `description`.
   - Checks if the image file exists; raises a `FileNotFoundError` if it doesn't.
   - Constructs an HTML string with embedded CSS for styling.
   - Writes the HTML content to a file named `gdp_report.html`.
   - Opens the generated HTML file in the default web browser using `webbrowser.open`.

2. **Function `main`**:
   - Defines the image path, title, and description for the GDP graph.
   - Calls `generate_html_page` with these parameters.

3. **Execution**:
   - The script is executed from the `main` block, which ensures that the HTML generation and browser opening happen when the script is run directly.

### Usage:
- Ensure you have a file named `gdp.png` in the same directory as the script.
- Run the script, and it will open a web browser displaying the HTML page with the image and description.