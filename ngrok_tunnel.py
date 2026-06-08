from pyngrok import ngrok

public_url = ngrok.connect(5000).public_url
print(public_url)
