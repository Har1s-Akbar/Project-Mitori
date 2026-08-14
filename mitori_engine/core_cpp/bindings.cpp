#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <optional>
#include <include/engine.hpp>
#include <include/utility_class.hpp>

namespace py = pybind11;

const uint64_t PRICE_PRECISION = 100000000;

PYBIND11_MODULE(mitori_engine, m){
    m.doc() = "Mitori Engine Python Bindings- C++ to python bridge";

    py::enum_<Side>(m, "Side")
        .value("BUY", Side::BUY)
        .value("SELL", Side::SELL);
    
    py::enum_<Type>(m, "Type")
        .value("LIMIT", Type::LIMIT)
        .value("MARKET", Type::MARKET);
        
    py::class_<Trade>(m, "Trade")
        .def_readonly("ticker", &Trade::ticker)
        .def_property_readonly("quantity", [](const Trade& t) {
            return static_cast<double>(t.quantity) / PRICE_PRECISION;
        })
        .def_readonly("buyer_id", &Trade::buyer_id)
        .def_readonly("seller_id", &Trade::seller_id)
        .def_property_readonly("price_locked_by_user", [](const Trade& t) {
            return static_cast<double>(t.price_locked_by_user) / PRICE_PRECISION;
        })
        .def_property_readonly("price_settled_at", [](const Trade& t) {
            return static_cast<double>(t.price_setteled_at) / PRICE_PRECISION;
        });

    py::class_<OrderBook>(m,"OrderBook")
        .def(py::init<std::string>())
        .def("process_order", [](OrderBook & book,
                    std::string order_id,
                    std::string order_owner_id,
                    Side side,
                    Type type,
                    bool is_canceled,
                    double price,
                    double number_of_shares,
                    std::optional<double> max_authorized_funds){
                        Order* order = ArenaAllocator::allocate();
                        order->order_id = order_id;
                        order->order_owner_id = order_owner_id;
                        order->type = type;
                        order->side = side;
                        order->number_of_shares = number_of_shares;
            
                        order->price = static_cast<uint64_t>(price * PRICE_PRECISION);
                        order->number_of_shares = static_cast<uint64_t>(number_of_shares * PRICE_PRECISION); 
                        if (max_authorized_funds.has_value()) {
                        order->max_authorized_funds = static_cast<uint64_t>(max_authorized_funds.value() * PRICE_PRECISION);
                        } else {
                        order->max_authorized_funds = UINT64_MAX; 
                        }
                        return book.process_order(order);
        })
        .def("get_current_bbo", [](OrderBook & book){
            auto bbo = book.get_current_bbo();
            std::unordered_map<std::string, double> scaled_bbo;
            scaled_bbo["best_ask_price"] = static_cast<double>(bbo["best_ask_price"]) / PRICE_PRECISION;
            scaled_bbo["best_bid_price"] = static_cast<double>(bbo["best_bid_price"]) / PRICE_PRECISION;
            return scaled_bbo;
        });
        m.def("reset_memory", &ArenaAllocator::reset, "Zero-latency allocator reset");
        m.def("cleanup_memory", &ArenaAllocator::cleanup, "Safely destroy memory slabs");
}