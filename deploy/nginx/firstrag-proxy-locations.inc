# Common FirstRAG proxy locations.
#
# Include this file inside a server block after setting server_name/listen/TLS.
# The frontend API proxy is the only public upstream. FastAPI and PostgreSQL
# should stay bound to loopback or private networking.

client_max_body_size 20m;
limit_req_status 429;

proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $firstrag_connection_upgrade;

proxy_connect_timeout 10s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;

add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

location = /healthz {
    access_log off;
    default_type text/plain;
    return 200 "ok\n";
}

location = /api/chat {
    limit_req zone=firstrag_chat burst=10 nodelay;
    proxy_buffering off;
    proxy_cache off;
    gzip off;
    add_header X-Accel-Buffering "no" always;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    proxy_pass http://firstrag_frontend;
}

location ~ ^/api/(login|register)$ {
    limit_req zone=firstrag_auth burst=5 nodelay;
    proxy_pass http://firstrag_frontend;
}

location ~ ^/api/chat/(knowledge-files/[^/]+/vectors|knowledge-base/[^/]+/vectors|vector-index-jobs)(/.*)?$ {
    limit_req zone=firstrag_vector burst=10 nodelay;
    proxy_pass http://firstrag_frontend;
}

location ~ ^/api/chat/(knowledge-files|knowledge-base/[^/]+/files)(/.*)?$ {
    limit_req zone=firstrag_upload burst=5 nodelay;
    proxy_request_buffering off;
    proxy_pass http://firstrag_frontend;
}

location ~ ^/api/settings(/.*)?$ {
    limit_req zone=firstrag_model burst=5 nodelay;
    proxy_pass http://firstrag_frontend;
}

location ^~ /api/ {
    limit_req zone=firstrag_api burst=30 nodelay;
    proxy_pass http://firstrag_frontend;
}

location / {
    proxy_pass http://firstrag_frontend;
}
