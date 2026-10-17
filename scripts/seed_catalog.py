"""Popula categorias e produtos de exemplo: python -m scripts.seed_catalog"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Category, Product
from app.services.catalog_service import placeholder_image

CATEGORIES = ["Freios", "Motor", "Suspensão", "Elétrica", "Filtros e Óleos"]

# nome, marca, categoria, preço, estoque, descrição
PRODUCTS = [
    ("Pastilha de Freio Dianteira", "Bosch", "Freios", 129.90, 25, "Pastilha cerâmica de alta durabilidade, baixo ruído."),
    ("Disco de Freio Ventilado", "Fremax", "Freios", 289.90, 12, "Par de discos ventilados para melhor dissipação de calor."),
    ("Vela de Ignição Iridium", "NGK", "Motor", 49.90, 60, "Vela de longa vida útil, melhor eficiência de combustível."),
    ("Correia Dentada", "Gates", "Motor", 89.90, 18, "Correia reforçada para motores 1.0 e 1.6."),
    ("Amortecedor Dianteiro", "Cofap", "Suspensão", 349.90, 8, "Amortecedor pressurizado a gás, conforto e estabilidade."),
    ("Kit Batente e Coifa", "Monroe", "Suspensão", 119.90, 0, "Kit completo para suspensão dianteira."),
    ("Bateria 60Ah", "Moura", "Elétrica", 459.90, 10, "Bateria livre de manutenção, 18 meses de garantia."),
    ("Lâmpada Farol H4 (par)", "Philips", "Elétrica", 79.90, 40, "Lâmpadas de maior luminosidade e alcance."),
    ("Filtro de Óleo", "Mann", "Filtros e Óleos", 29.90, 100, "Filtro com alta capacidade de retenção de impurezas."),
    ("Óleo 5W30 Sintético 1L", "Mobil", "Filtros e Óleos", 54.90, 70, "Óleo sintético para motores flex modernos."),
    ("Filtro de Ar", "Tecfil", "Filtros e Óleos", 39.90, 45, "Filtro de ar do motor, encaixe perfeito."),
    ("Bomba de Combustível", "Bosch", "Motor", 219.90, 6, "Bomba elétrica com alta vazão e baixo ruído."),
]


def main() -> None:
    with SessionLocal() as db:
        categories = {c.name: c for c in db.scalars(select(Category))}
        for name in CATEGORIES:
            if name not in categories:
                category = Category(name=name)
                db.add(category)
                categories[name] = category
        db.flush()

        existing = set(db.scalars(select(Product.name)))
        created = 0
        for name, brand, category, price, stock, description in PRODUCTS:
            if name in existing:
                continue
            db.add(
                Product(
                    name=name,
                    brand=brand,
                    description=description,
                    price=price,
                    stock=stock,
                    image_url=placeholder_image(name),
                    category_id=categories[category].id,
                )
            )
            created += 1

        db.commit()
        print(f"Categorias: {len(categories)} | produtos novos: {created}")


if __name__ == "__main__":
    main()