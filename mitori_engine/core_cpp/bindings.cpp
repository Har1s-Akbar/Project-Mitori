#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <optional>
#include <chrono>   
#include <vector>   
#include "../include/engine.hpp"
#include "../include/utility_class.hpp"
#include <x86intrin.h>
#include <thread>
#include <pybind11/numpy.h>

namespace py = pybind11;

struct RawOrderData {
    unsigned __int128 full_order_id;
    unsigned __int128 full_owner_id;
    Type type;
    Side side;
    bool is_canceled;
    uint64_t price;
    uint64_t number_of_shares;
    uint64_t max_authorized_funds;
};

PYBIND11_MODULE(mitori_engine_cpp, m){
    m.doc() = "Mitori Engine Python Bindings- C++ to python bridge";
    py::enum_<Side>(m, "Side")
        .value("BUY", Side::BUY)
        .value("SELL", Side::SELL)
        .export_values();
    
    py::enum_<Type>(m, "Type")
        .value("LIMIT", Type::LIMIT)
        .value("MARKET", Type::MARKET)
        .export_values();

    py::class_<Trade>(m, "Trade")
        .def_readonly("ticker", &Trade::ticker)
        
        .def_readonly("price_locked_by_user", &Trade::price_locked_by_user)
        .def_readonly("price_setteled_at", &Trade::price_setteled_at)
        .def_readonly("quantity", &Trade::quantity)
        .def_property_readonly("buyer_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id >> 64); })
        .def_property_readonly("buyer_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id); })
        .def_property_readonly("seller_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id >> 64); })
        .def_property_readonly("seller_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id); });
        
    py::class_<OrderBook>(m,"OrderBook")
        .def(py::init<std::string>(), py::arg("ticker"))
        .def("process_order", [](OrderBook & book,
                    uint64_t order_id_high , uint64_t order_id_low,
                    uint64_t order_owner_id_high, uint64_t order_owner_id_low,
                    Side side,
                    Type type,
                    bool is_canceled,
                    uint64_t price,
                    uint64_t number_of_shares,
                    std::optional<uint64_t> max_authorized_funds){
                        std::lock_guard<std::mutex> lock(book.engine_mutex);
                        
                        uint32_t order_index = ArenaAllocator::allocate_index();
                        Order* order = ArenaAllocator::get_order(order_index);
                        
                        unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;
                        unsigned __int128 full_owner_id = (static_cast<unsigned __int128>(order_owner_id_high) << 64) | order_owner_id_low;
                        
                        uint32_t current_meta_index = book.metadata_vault.size();
                        book.metadata_vault.push_back({full_order_id, full_owner_id});
                        
                        order->metadata_index = current_meta_index;
                        order->type = type;
                        order->side = side;
                        order->is_canceled = is_canceled;
                        order->price = price;
                        order->number_of_shares = number_of_shares;
                                                
                        if (max_authorized_funds.has_value()) {
                            order->max_authorized_funds = max_authorized_funds.value();
                        } else {
                            order->max_authorized_funds = UINT64_MAX; 
                        }
                        return book.process_order(order_index);
        },
            py::call_guard<py::gil_scoped_release>(),
            py::arg("order_id_high"),
            py::arg("order_id_low"),
            py::arg("order_owner_id_high"),
            py::arg("order_owner_id_low"),
            py::arg("side"),
            py::arg("type"),
            py::arg("is_canceled"),
            py::arg("price"),
            py::arg("number_of_shares"),
            py::arg("max_authorized_funds") = std::nullopt)

        .def("benchmark_batch", [](OrderBook & book, py::list orders_list, size_t warmup_count = 5000) {
            std::vector<uint32_t> batch_indices;
            batch_indices.reserve(orders_list.size());
            
            for (auto item : orders_list) {
                py::dict py_order = item.cast<py::dict>();
                
                uint32_t order_index = ArenaAllocator::allocate_index();
                Order* order = ArenaAllocator::get_order(order_index);
                
                uint64_t order_id_high = py_order["order_id_high"].cast<uint64_t>();
                uint64_t order_id_low = py_order["order_id_low"].cast<uint64_t>();
                uint64_t owner_id_high = py_order["order_owner_id_high"].cast<uint64_t>();
                uint64_t owner_id_low = py_order["order_owner_id_low"].cast<uint64_t>();
                
                unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;
                unsigned __int128 full_owner_id = (static_cast<unsigned __int128>(owner_id_high) << 64) | owner_id_low;
                
                uint32_t current_meta_index = book.metadata_vault.size();
                book.metadata_vault.push_back({full_order_id, full_owner_id});
                
                order->metadata_index = current_meta_index;
                order->type = py_order["type"].cast<Type>();
                order->side = py_order["side"].cast<Side>();
                order->is_canceled = py_order["is_canceled"].cast<bool>();
                order->price = py_order["price"].cast<uint64_t>();
                order->number_of_shares = py_order["number_of_shares"].cast<uint64_t>();
                
                if (py_order.contains("max_authorized_funds") && !py_order["max_authorized_funds"].is_none()) {
                    order->max_authorized_funds = py_order["max_authorized_funds"].cast<uint64_t>();
                } else {
                    order->max_authorized_funds = UINT64_MAX;
                }
                
                batch_indices.push_back(order_index);
            }
            py::gil_scoped_release release;
            std::lock_guard<std::mutex> lock(book.engine_mutex);
            //Implementing and replacing the chrono with intrinsic TSC register read.
            auto t1 = std::chrono::high_resolution_clock::now();
            unsigned int aux;
            uint64_t c1 = __rdtscp(&aux);
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
            uint64_t c2 = __rdtscp(&aux);
            auto t2 = std::chrono::high_resolution_clock::now();
            double tsc_to_ns = static_cast<double>(std::chrono::duration_cast<std::chrono::nanoseconds>(t2 - t1).count()) / (c2 - c1);

            size_t timing_count = (batch_indices.size() > warmup_count) ? (batch_indices.size() - warmup_count) : 0;
            
            std::vector<uint64_t> latencies(timing_count, 0);
            
            size_t i = 0;
            
            for (; i < warmup_count && i < batch_indices.size(); ++i) {
                book.process_order(batch_indices[i]);
            }

            size_t timing_index = 0;
            for (; i < batch_indices.size(); ++i) {
                uint64_t start = __rdtscp(&aux);
                
                book.process_order(batch_indices[i]);
                
                uint64_t end = __rdtscp(&aux);
                
                latencies[timing_index++] = static_cast<uint64_t>((end - start) * tsc_to_ns);
            }
            return latencies;
        }, 
        
            py::arg("orders_list"), 
            py::arg("warmup_count") = 5000)
            
        .def("benchmark_closed_loop", [](OrderBook & book, py::dict numpy_orders, uint64_t target_rps_per_thread, uint64_t duration_sec, size_t warmup_count) {
            auto arr_oid_h = numpy_orders["order_id_high"].cast<py::array_t<uint64_t>>().unchecked<1>();
            auto arr_oid_l = numpy_orders["order_id_low"].cast<py::array_t<uint64_t>>().unchecked<1>();
            auto arr_own_h = numpy_orders["order_owner_id_high"].cast<py::array_t<uint64_t>>().unchecked<1>();
            auto arr_own_l = numpy_orders["order_owner_id_low"].cast<py::array_t<uint64_t>>().unchecked<1>();
            auto arr_side = numpy_orders["side"].cast<py::array_t<uint8_t>>().unchecked<1>();
            auto arr_type = numpy_orders["type"].cast<py::array_t<uint8_t>>().unchecked<1>();
            auto arr_iscanc = numpy_orders["is_canceled"].cast<py::array_t<bool>>().unchecked<1>();
            auto arr_price = numpy_orders["price"].cast<py::array_t<uint64_t>>().unchecked<1>();
            auto arr_shares = numpy_orders["number_of_shares"].cast<py::array_t<uint64_t>>().unchecked<1>();
            auto arr_max_f = numpy_orders["max_authorized_funds"].cast<py::array_t<uint64_t>>().unchecked<1>();

            size_t num_orders = arr_oid_h.shape(0);
            std::vector<RawOrderData> active_stream_cache;
            active_stream_cache.reserve(num_orders);

            // 1. Ultra-fast NumPy Unboxing
            for (size_t i = 0; i < num_orders; ++i) {
                RawOrderData raw;
                raw.full_order_id = (static_cast<unsigned __int128>(arr_oid_h(i)) << 64) | arr_oid_l(i);
                raw.full_owner_id = (static_cast<unsigned __int128>(arr_own_h(i)) << 64) | arr_own_l(i);
                raw.type = static_cast<Type>(arr_type(i));
                raw.side = static_cast<Side>(arr_side(i));
                raw.is_canceled = arr_iscanc(i);
                raw.price = arr_price(i);
                raw.number_of_shares = arr_shares(i);
                raw.max_authorized_funds = arr_max_f(i);
                active_stream_cache.push_back(raw);
            }

            uint64_t interval_ns = 1'000'000'000 / target_rps_per_thread;
            uint64_t max_expected_orders = target_rps_per_thread * duration_sec * 1.1;

            py::array_t<uint64_t> service_times_np(max_expected_orders);
            py::array_t<uint64_t> queue_times_np(max_expected_orders);
            
            uint64_t* srv_ptr = service_times_np.mutable_data();
            uint64_t* que_ptr = queue_times_np.mutable_data();

            size_t processed_count = 0;
            size_t buffer_size = active_stream_cache.size();

            {
                py::gil_scoped_release release;

                auto t1 = std::chrono::high_resolution_clock::now();
                unsigned int aux;
                uint64_t c1 = __rdtscp(&aux);
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
                uint64_t c2 = __rdtscp(&aux);
                auto t2 = std::chrono::high_resolution_clock::now();
                double tsc_to_ns = static_cast<double>(std::chrono::duration_cast<std::chrono::nanoseconds>(t2 - t1).count()) / (c2 - c1);
                
                uint64_t start_tsc = __rdtscp(&aux);
                uint64_t duration_tsc = (duration_sec * 1'000'000'000) / tsc_to_ns;
                uint64_t end_tsc = start_tsc + duration_tsc;
                uint64_t interval_tsc = interval_ns / tsc_to_ns;

                for (size_t i = 0; i < warmup_count && i < active_stream_cache.size(); ++i) {
                    const RawOrderData& raw = active_stream_cache[i];
                    std::lock_guard<std::mutex> match_lock(book.engine_mutex);
                    
                    uint32_t order_index = ArenaAllocator::allocate_index();
                    Order* order = ArenaAllocator::get_order(order_index);
                    uint32_t current_meta_index = book.metadata_vault.size();
                    book.metadata_vault.push_back(OrderMetadata{raw.full_order_id, raw.full_owner_id});
                    
                    order->metadata_index = current_meta_index;
                    order->type = raw.type;
                    order->side = raw.side;
                    order->is_canceled = raw.is_canceled;
                    order->price = raw.price;
                    order->number_of_shares = raw.number_of_shares;
                    order->max_authorized_funds = raw.max_authorized_funds;
                    
                    book.process_order(order_index); 
                }
                
                uint64_t lock_acquired_tsc = 0; 
                uint64_t completion_tsc = 0;    
                
                while (__rdtscp(&aux) < end_tsc && processed_count < max_expected_orders) {
                    const RawOrderData& raw = active_stream_cache[(warmup_count + processed_count) % buffer_size];
                    uint64_t expected_arrival_tsc = start_tsc + (processed_count * interval_tsc);
                    
                    while (__rdtscp(&aux) < expected_arrival_tsc) { }
                    
                    {
                        std::lock_guard<std::mutex> match_lock(book.engine_mutex);
                        lock_acquired_tsc = __rdtscp(&aux); // OS granted the lock
                        
                        uint32_t order_index = ArenaAllocator::allocate_index();
                        Order* order = ArenaAllocator::get_order(order_index);
                        uint32_t current_meta_index = book.metadata_vault.size();
                        book.metadata_vault.push_back(OrderMetadata{raw.full_order_id, raw.full_owner_id});
                        
                        order->metadata_index = current_meta_index;
                        order->type = raw.type;
                        order->side = raw.side;
                        order->is_canceled = raw.is_canceled;
                        order->price = raw.price;
                        order->number_of_shares = raw.number_of_shares;
                        order->max_authorized_funds = raw.max_authorized_funds;
                        
                        book.process_order(order_index); 
                        completion_tsc = __rdtscp(&aux); 
                    }
                    
                    srv_ptr[processed_count] = static_cast<uint64_t>((completion_tsc - lock_acquired_tsc) * tsc_to_ns);
                    que_ptr[processed_count] = static_cast<uint64_t>((lock_acquired_tsc - expected_arrival_tsc) * tsc_to_ns);
                    
                    processed_count++;
                }
            }
            
            return py::make_tuple(service_times_np, queue_times_np, processed_count);
        }, 
            py::arg("numpy_orders"), 
            py::arg("target_rps_per_thread"),
            py::arg("duration_sec"),
            py::arg("warmup_count") = 0)

        .def("get_book_depth", [](OrderBook &book) {
            py::gil_scoped_release release;
            std::lock_guard<std::mutex> lock(book.engine_mutex);
            return book.get_book_depth();
        })

        .def("get_bid_length", [](OrderBook &book) {
            py::gil_scoped_release release;
            std::lock_guard<std::mutex> lock(book.engine_mutex);
            return book.get_bid_length();
        })

        .def("get_ask_length", [](OrderBook &book) {
            py::gil_scoped_release release;
            std::lock_guard<std::mutex> lock(book.engine_mutex);
            return book.get_ask_length();
        })

        .def("tombstone_delete", [](OrderBook& book, uint64_t order_id_high, uint64_t order_id_low)-> py::object {
            unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;
            py::gil_scoped_release release;
            std::lock_guard<std::mutex> lock(book.engine_mutex);
            Order* canceled_order = book.tombstone_delete(full_order_id);

            if(!canceled_order){
                return py::none();
            }
            unsigned __int128 owner_id = book.metadata_vault[canceled_order->metadata_index].owner_id;
            uint64_t owner_id_high = static_cast<uint64_t>(owner_id >> 64);
            uint64_t owner_id_low = static_cast<uint64_t>(owner_id);

            py::dict result;
            result["owner_id_high"] = owner_id_high;
            result["owner_id_low"] = owner_id_low;
            result["side"] = canceled_order->side;
            result["type"] = canceled_order->type;
            result["price"] = canceled_order->price;
            result["number_of_shares"] = canceled_order->number_of_shares;
            result["is_canceled"] = canceled_order->is_canceled; 

            return result;
        },
            py::arg("order_id_high"),
            py::arg("order_id_low")
        )
        .def("get_current_bbo", &OrderBook::get_current_bbo, py::call_guard<py::gil_scoped_release>())
        .def("reset_engine", &OrderBook::reset_engine, py::call_guard<py::gil_scoped_release>());
        m.def("cleanup_memory", &ArenaAllocator::cleanup, py::call_guard<py::gil_scoped_release>());
}