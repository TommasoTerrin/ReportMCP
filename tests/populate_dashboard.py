"""
Script per popolare il server ReportMCP già attivo.
"""
import httpx
import asyncio
import json

async def populate():
    url = "http://localhost:8050"
    session_id = "test_ristorante_api_2024"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"🚀 Iniziando popolamento per sessione: {session_id}")
        
        # 1. Ingestion
        data = [
            {"prodotto": "Pizza Margherita", "quantita": 150, "categoria": "Pizza", "prezzo_medio": 8.50},
            {"prodotto": "Pizza Diavola", "quantita": 120, "categoria": "Pizza", "prezzo_medio": 9.00},
            {"prodotto": "Pasta Carbonara", "quantita": 95, "categoria": "Pasta", "prezzo_medio": 12.00},
            {"prodotto": "Pasta Amatriciana", "quantita": 80, "categoria": "Pasta", "prezzo_medio": 11.50},
            {"prodotto": "Risotto ai Funghi", "quantita": 60, "categoria": "Risotti", "prezzo_medio": 14.00},
            {"prodotto": "Insalata Mista", "quantita": 75, "categoria": "Contorni", "prezzo_medio": 6.00},
            {"prodotto": "Tiramisù", "quantita": 110, "categoria": "Dolci", "prezzo_medio": 7.00},
            {"prodotto": "Acqua Naturale", "quantita": 200, "categoria": "Bevande", "prezzo_medio": 2.50},
        ]
        
        schema = [
            {"name": "prodotto", "type": "string", "is_dimension": True},
            {"name": "quantita", "type": "integer", "is_metric": True},
            {"name": "categoria", "type": "string", "is_dimension": True},
            {"name": "prezzo_medio", "type": "float", "is_metric": True},
        ]
        
        print("📤 Ingestion dati...")
        await client.post(f"{url}/api/ingest", json={
            "session_id": session_id,
            "table_name": "menu_ristorante",
            "data": data,
            "schema": schema
        })
        
        # 2. Creazione Dashboard
        print("🎨 Creazione dashboard dinamica...")
        components = [
            {"type": "h1", "text": "📊 Dashboard Vendite Ristorante 2024"},
            {"type": "p", "text": "Bentornato! Questa dashboard è stata generata automaticamente con i tuoi seed data."},
            {
                "type": "alert",
                "text": "💡 Suggerimento: La Pizza Margherita è il tuo prodotto più venduto per volume!",
                "color": "info"
            },
            {
                "type": "kpi_card", 
                "title": "Unità Vendute", 
                "metric": "quantita", 
                "aggregation": "sum", 
                "table": "menu_ristorante", 
                "icon": "fa-shopping-cart", 
                "color": "primary"
            },
            {
                "type": "kpi_card", 
                "title": "Ticket Medi!", 
                "metric": "prezzo_medio", 
                "aggregation": "avg", 
                "table": "menu_ristorante", 
                "icon": "fa-euro-sign", 
                "color": "success"
            },
            {
                "type": "bar_chart", 
                "title": "Mix Vendite per Categoria", 
                "x_axis": "categoria", 
                "y_axis": "quantita", 
                "table": "menu_ristorante", 
                "aggregation": "sum"
            },
            {"type": "p", "text": "Analisi della distribuzione delle vendite per categoria merceologica."},
            {"type": "table", "table": "menu_ristorante", "page_size": 10}
        ]
        
        resp = await client.post(f"{url}/api/create", json={
            "session_id": session_id,
            "title": "Analytics Dashboard",
            "components": components
        })
        
        if resp.status_code == 200:
            print(f"✅ Dashboard pronta su: {url}/dashboard/{session_id}")
        else:
            print(f"❌ Errore: {resp.text}")

if __name__ == "__main__":
    asyncio.run(populate())
