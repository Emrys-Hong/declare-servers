1. set up dns servers:
   Type: A
   Host: serverapi
   Value: IP address of your server (e.g., 157.230.44.85)
   TTL: 60 min or default

2. in `/etc/nginx/sites-available/serverapi.piphi.dev`
   create

```
server {
    listen 80;
    server_name serverapi.piphi.dev;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # To enable HTTPS, you would need to also configure SSL here
}
sudo ln -s /etc/nginx/sites-available/serverapi.piphi.dev /etc/nginx/sites-enabled/
sudo nginx -t
```

3. restart service

```bash
sudo systemctl restart nginx
```

4. ssl certificate

```bash
# sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx
# sudo certbot renew --dry-run
```

5.

```bash
uvicorn main:app --reload --port 5000
```

6. set server time
```
sudo timedatectl set-timezone Asia/Singapore
```
